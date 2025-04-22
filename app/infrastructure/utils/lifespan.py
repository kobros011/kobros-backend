from contextlib import asynccontextmanager
from app.infrastructure.dababase.db import create_tables, async_session
from fastapi import FastAPI
from ..models.user_model import UserModel
from sqlalchemy import select
from app.core.auth import get_password_hash
from ...domain.entities.user import User


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()

    async with async_session() as session:
        async with session.begin():
            names = ["admin.deibi", "admin.carlos"]
            exists_admin = await session.scalar(
                select(UserModel.username).where(UserModel.username.in_(names))
            )

            if not exists_admin:
                session.add_all(
                    [
                        UserModel(**User(
                            type_user="admin",
                            username="admin.david",
                            name="David",
                            last_name="Agudelo",
                            hashed_password=get_password_hash("m4?L77"),
                        ).__dict__),
                        UserModel(**User(
                            type_user="admin",
                            username="admin.carlos",
                            name="Carlos",
                            last_name="Garcia",
                            hashed_password=get_password_hash("F_8f15"),
                        ).__dict__),
                    ]
                )
    yield
