import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from wallybot.infrastructure.loop import selector_loop
from wallybot.infrastructure.models import Base
from wallybot.infrastructure.settings import load_settings


def migrate(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def online():
    engine = create_async_engine(load_settings().database_url.get_secret_value())
    async with engine.connect() as connection:
        await connection.run_sync(migrate)
    await engine.dispose()


with asyncio.Runner(loop_factory=selector_loop) as runner:
    runner.run(online())
