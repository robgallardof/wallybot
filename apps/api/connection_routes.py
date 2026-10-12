import time
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from apps.api.dependencies import Admin, SignedIn
from apps.api.dto import ProviderConnectionListView, ProviderConnectionView
from apps.api.schemas import ProviderConnectionCreate
from wallybot.exchanges.kraken_private import (
    KrakenPrivateError,
    spot_balances,
    validate_permissions,
)
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
        transport = request.app.state.kraken_private_factory(body.api_key, body.api_secret)
        try:
            validate_permissions(await transport.call("GetApiKeyInfo", {}))
            spot_balances(await transport.call("BalanceEx", {}))
        except (KrakenPrivateError, ValueError, KeyError):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Cannot verify Kraken spot permissions and balances. Use query and order "
                    "permissions only, without funding or withdrawal permissions."
                ),
            ) from None
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
