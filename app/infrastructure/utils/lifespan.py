from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Bootstrap de usuarios dev: scripts/ensure_dev_users.py en el entrypoint de deploy.
    yield
