import time
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from apps.api.dependencies import Admin, SignedIn
from apps.api.dto import ProviderConnectionListView, ProviderConnectionView
from apps.api.schemas import ProviderConnectionCreate, ProviderConnectionUpdate
from wallybot.exchanges.private_errors import ExchangePrivateError
from wallybot.infrastructure.live_models import LiveControlRow
from wallybot.infrastructure.models import ProviderConnectionRow
from wallybot.infrastructure.provider_connection_repository import ProviderConnectionRepository
from wallybot.security.auth import audit

router = APIRouter(prefix="/api/connections", tags=["connections"])


def _view(row: ProviderConnectionRow) -> ProviderConnectionView:
    return ProviderConnectionView(
        id=row.id,
        provider=row.provider,
        label=row.label,
        mode=row.mode,
        status=row.status,
        has_credentials=row.encrypted_key is not None,
        created_at=row.created_at,
    )


async def _verify_trading_key(
    request: Request, provider: str, api_key: str, api_secret: str
) -> None:
    factory = (
        request.app.state.binance_private_factory
        if provider == "BINANCE"
        else request.app.state.kraken_private_factory
    )
    venue = request.app.state.live_trading.venue(provider)
    transport = factory(api_key, api_secret)
    try:
        # Verification reads permissions and balances only; it never places an order.
        await venue.verify_key(transport)
        await venue.balances(transport)
    except ExchangePrivateError as exc:
        # Messages are sanitized by construction and tell the operator what to fix.
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=409,
            detail="The exchange returned balances in an unexpected format; nothing was saved",
        ) from None


@router.get("", response_model=ProviderConnectionListView)
async def list_connections(request: Request, user: SignedIn) -> ProviderConnectionListView:
    async with request.app.state.sessions() as db:
        rows = await ProviderConnectionRepository(db).list_for_user(user.id)
    return ProviderConnectionListView(rows=[_view(row) for row in rows])


@router.post("", response_model=ProviderConnectionView)
async def add_connection(
    body: ProviderConnectionCreate, request: Request, user: Admin
) -> ProviderConnectionView:
    crypto = request.app.state.auth.crypto
    status = "PENDING"
    if body.mode == "TRADE_ONLY":
        await _verify_trading_key(request, body.provider, body.api_key, body.api_secret)
        status = "HEALTHY"
    connection = ProviderConnectionRow(
        id=str(uuid4()),
        user_id=user.id,
        provider=body.provider,
        label=body.label.strip(),
        mode=body.mode,
        status=status,
        encrypted_key=crypto.encrypt(body.api_key) if body.api_key else None,
        encrypted_secret=crypto.encrypt(body.api_secret) if body.api_secret else None,
        created_at=int(time.time()),
    )
    async with request.app.state.sessions.begin() as db:
        await ProviderConnectionRepository(db).add(connection)
        audit(db, "PROVIDER_CONNECTION_ADDED_" + body.mode, user.id)
    return _view(connection)


@router.post("/{connection_id}", response_model=ProviderConnectionView)
async def update_connection(
    connection_id: str, body: ProviderConnectionUpdate, request: Request, user: Admin
) -> ProviderConnectionView:
    crypto = request.app.state.auth.crypto
    async with request.app.state.sessions() as db:
        row = await db.get(ProviderConnectionRow, connection_id)
        live = await db.get(LiveControlRow, 1)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Connection not found")
    if body.mode == "TRADE_ONLY" and row.provider not in {"KRAKEN", "BINANCE"}:
        raise HTTPException(
            status_code=422, detail="Spot trading connections require a Kraken or Binance key"
        )
    changes_credentials = bool(body.api_key or body.api_secret)
    if (
        live is not None
        and live.connection_id == row.id
        and (body.mode != row.mode or changes_credentials)
    ):
        raise HTTPException(
            status_code=409,
            detail="This connection is the real trading account; disable real trading first",
        )
    api_key = body.api_key or (crypto.decrypt(row.encrypted_key) if row.encrypted_key else None)
    api_secret = body.api_secret or (
        crypto.decrypt(row.encrypted_secret) if row.encrypted_secret else None
    )
    status = row.status if body.mode == row.mode and not changes_credentials else "PENDING"
    if body.mode == "TRADE_ONLY":
        if not api_key or not api_secret:
            raise HTTPException(
                status_code=422,
                detail="Spot trading connections require a Kraken or Binance key and secret",
            )
        await _verify_trading_key(request, row.provider, api_key, api_secret)
        status = "HEALTHY"
    async with request.app.state.sessions.begin() as db:
        stored = await db.get(ProviderConnectionRow, connection_id, with_for_update=True)
        stored.label = body.label.strip()
        stored.mode = body.mode
        stored.status = status
        if body.api_key:
            stored.encrypted_key = crypto.encrypt(body.api_key)
        if body.api_secret:
            stored.encrypted_secret = crypto.encrypt(body.api_secret)
        audit(db, "PROVIDER_CONNECTION_UPDATED_" + body.mode, user.id)
    return _view(stored)
