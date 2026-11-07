import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

load_dotenv()

# Import Base and all models so their tables are registered in Base.metadata
from app.infrastructure.dababase.base_class import Base
from app.infrastructure.models.user_model import UserModel  # noqa: F401
from app.infrastructure.models.brand_model import BrandModel  # noqa: F401
from app.infrastructure.models.client_model import ClientModel  # noqa: F401
from app.infrastructure.models.route_model import RouteModel  # noqa: F401
from app.infrastructure.models.client_route_model import ClientRouteModel  # noqa: F401
from app.infrastructure.models.loan_model import LoanModel  # noqa: F401
from app.infrastructure.models.payment_model import PaymentModel  # noqa: F401
from app.infrastructure.models.expense_model import ExpenseModel  # noqa: F401
from app.infrastructure.models.liquidation_model import LiquidationModel  # noqa: F401
from app.infrastructure.models.client_reference_model import ClientReferenceModel  # noqa: F401
from app.infrastructure.models.route_movement_model import RouteMovementModel  # noqa: F401
from app.infrastructure.models.models import UserType  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    url = os.getenv("DATABASE_URL", "postgresql+asyncpg://root:admin@db:5432/cobros")
    # Alembic uses psycopg2 (sync) for migrations only
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
