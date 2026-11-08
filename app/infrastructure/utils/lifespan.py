import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.infrastructure.utils.default_scheduler import enabled, loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Bootstrap de usuarios dev: scripts/ensure_dev_users.py en el entrypoint de deploy.
    task = asyncio.create_task(loop()) if enabled() else None  # mora diaria sin worker
    try:
        yield
    finally:
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
