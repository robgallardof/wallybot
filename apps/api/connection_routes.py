import time
from uuid import uuid4

from fastapi import APIRouter, Request

from apps.api.dependencies import Admin, SignedIn
from apps.api.dto import ProviderConnectionListView, ProviderConnectionView
from apps.api.schemas import ProviderConnectionCreate
from wallybot.infrastructure.models import ProviderConnectionRow
from wallybot.infrastructure.provider_connection_repository import ProviderConnectionRepository

router = APIRouter(prefix="/api/connections", tags=["connections"])


def _view(row: ProviderConnectionRow) -> ProviderConnectionView:
    return ProviderConnectionView(
        id=row.id,
        provider=row.provider,
        label=row.label,
        mode=row.mode,
        status=row.status,
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
    connection = ProviderConnectionRow(
        id=str(uuid4()),
        user_id=user.id,
        provider=body.provider,
        label=body.label.strip(),
        mode=body.mode,
        status="PENDING",
        created_at=int(time.time()),
    )
    async with request.app.state.sessions.begin() as db:
        await ProviderConnectionRepository(db).add(connection)
    return _view(connection)
