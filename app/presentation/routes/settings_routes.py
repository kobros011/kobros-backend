from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.currencies import catalog
from ...infrastructure.dababase.db import get_db
from ...infrastructure.models.user_model import UserModel
from ...infrastructure.storage.azure_blob import AzureBlobStorage, get_storage
from ...infrastructure.utils.require_authentication import require_authentication
from ...infrastructure.utils.require_role import require_role
from ...use_cases.settings_cases import MAX_LOGO_BYTES, SettingsUseCases
from ..shemas.settings_shema import LogoVariant, SettingsRead, SettingsUpdate

router = APIRouter(dependencies=[Depends(require_authentication)])

_MANAGE_ROLES = ("01", "02")  # dev, super


def get_settings_usecases(
    user: UserModel = Depends(require_authentication),
    db: AsyncSession = Depends(get_db),
    storage: AzureBlobStorage = Depends(get_storage),
) -> SettingsUseCases:
    usecases = SettingsUseCases(db=db, storage=storage)
    usecases.user = user
    return usecases


@router.get("/", response_model=SettingsRead)
async def read_settings(
    brand_id: Optional[UUID] = None,
    usecases: SettingsUseCases = Depends(get_settings_usecases),
):
    return await usecases.get_settings(brand_id)


@router.get("/currencies")
async def read_currency_catalog():
    """Monedas que una marca puede elegir (código, nombre, símbolo y decimales)."""
    return catalog()


@router.put("/", response_model=SettingsRead)
async def update_settings(
    data: SettingsUpdate,
    brand_id: Optional[UUID] = None,
    _: UserModel = Depends(require_role(*_MANAGE_ROLES)),
    usecases: SettingsUseCases = Depends(get_settings_usecases),
):
    return await usecases.update_settings(brand_id, data)


@router.post("/logo", response_model=SettingsRead)
async def upload_logo(
    variant: LogoVariant,
    brand_id: Optional[UUID] = None,
    file: UploadFile = File(...),
    _: UserModel = Depends(require_role(*_MANAGE_ROLES)),
    usecases: SettingsUseCases = Depends(get_settings_usecases),
):
    data = await file.read(MAX_LOGO_BYTES + 1)
    return await usecases.upload_logo(brand_id, variant, data)


@router.delete("/logo", response_model=SettingsRead)
async def delete_logo(
    variant: LogoVariant,
    brand_id: Optional[UUID] = None,
    _: UserModel = Depends(require_role(*_MANAGE_ROLES)),
    usecases: SettingsUseCases = Depends(get_settings_usecases),
):
    return await usecases.delete_logo(brand_id, variant)
