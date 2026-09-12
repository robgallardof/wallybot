import asyncio


def selector_loop() -> asyncio.AbstractEventLoop:
    """Psycopg async connections require a selector loop on Windows."""
    return asyncio.SelectorEventLoop()
