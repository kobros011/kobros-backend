import re
import uuid
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.exceptions import AppException, ConflictException, NotFoundException
from app.core.currencies import is_valid
from app.infrastructure.models.brand_model import BrandModel
from app.infrastructure.models.route_model import RouteModel
from app.infrastructure.models.brand_settings_model import BrandSettingsModel
from app.infrastructure.models.user_model import UserModel
from app.infrastructure.storage.azure_blob import AzureBlobStorage
from app.infrastructure.storage.logo_normalize import normalize_logo
from app.presentation.shemas.settings_shema import LogoVariant, SettingsRead, SettingsUpdate

MAX_LOGO_BYTES = 5 * 1024 * 1024
_UNSAFE_SVG = re.compile(rb"<script|<foreignobject|javascript:|\son\w+\s*=|<iframe|<!entity", re.IGNORECASE)
_LOGO_VARIANTS: tuple[LogoVariant, ...] = ("full", "mark")


def _role(user: UserModel) -> str:
    return user.type_user.value if hasattr(user.type_user, "value") else str(user.type_user)


def detect_image(data: bytes) -> Optional[tuple[str, str]]:
    """(content_type, extensión) según los bytes reales; None si no es un formato permitido."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    head = data[:2048].lstrip().lower()
    if b"<svg" in data[:4096].lower() and (head.startswith(b"<svg") or head.startswith(b"<?xml") or head.startswith(b"<!doctype svg")):
        if _UNSAFE_SVG.search(data):
            return None
        return "image/svg+xml", "svg"
    return None


class SettingsUseCases:
    user: Optional[UserModel] = None

    def __init__(self, db: AsyncSession, storage: AzureBlobStorage):
        self.db = db
        self.storage = storage

    # ---- resolución de marca -------------------------------------------------
    def _resolve_brand_id(self, requested: Optional[UUID], *, required: bool) -> Optional[UUID]:
        if _role(self.user) == "01":  # dev: elige la marca
            if requested is None and required:
                raise AppException("Debes elegir una marca", status_code=400)
            return requested
        if not self.user.brand_id:
            raise AppException("El usuario no tiene marca asociada", status_code=400)
        if requested is not None and requested != self.user.brand_id:
            raise AppException("Sin permisos sobre esta marca", status_code=403)
        return self.user.brand_id

    async def _get_brand(self, brand_id: UUID) -> BrandModel:
        brand = (await self.db.execute(select(BrandModel).where(BrandModel.id == brand_id))).scalars().first()
        if not brand:
            raise NotFoundException("La marca no fue encontrada")
        return brand

    async def _get_or_create(self, brand_id: UUID) -> BrandSettingsModel:
        model = (await self.db.execute(
            select(BrandSettingsModel).where(BrandSettingsModel.brand_id == brand_id)
        )).scalars().first()
        if not model:
            model = BrandSettingsModel(brand_id=brand_id)
            self.db.add(model)
            await self.db.flush()
        return model

    def _to_read(self, brand: BrandModel, model: Optional[BrandSettingsModel]) -> SettingsRead:
        return SettingsRead(
            brand_id=brand.id,
            brand_name=brand.name,
            brand_code=brand.code,
            contact_email=model.contact_email if model else None,
            contact_phone=model.contact_phone if model else None,
            app_name=model.app_name if model else None,
            primary_color=model.primary_color if model else None,
            logo_full_url=self.storage.url_for(model.logo_full_blob) if model else None,
            logo_full_width=model.logo_full_width if model else None,
            logo_full_height=model.logo_full_height if model else None,
            logo_full_tone=model.logo_full_tone if model else None,
            logo_mark_url=self.storage.url_for(model.logo_mark_blob) if model else None,
            logo_mark_width=model.logo_mark_width if model else None,
            logo_mark_height=model.logo_mark_height if model else None,
            logo_mark_tone=model.logo_mark_tone if model else None,
            number_format_style=(model.number_format_style if model else "comma-thousands"),
            number_decimals=(model.number_decimals if model else 2),
            currencies=list(model.currencies or []) if model else [],
            logo_enabled=self.storage.is_configured,
        )

    # ---- casos de uso --------------------------------------------------------
    async def get_settings(self, brand_id: Optional[UUID]) -> SettingsRead:
        brand_id = self._resolve_brand_id(brand_id, required=False)
        if brand_id is None:  # dev sin marca elegida: valores por defecto
            return SettingsRead(logo_enabled=self.storage.is_configured)
        brand = await self._get_brand(brand_id)
        model = (await self.db.execute(
            select(BrandSettingsModel).where(BrandSettingsModel.brand_id == brand_id)
        )).scalars().first()
        return self._to_read(brand, model)

    async def update_settings(self, brand_id: Optional[UUID], data: SettingsUpdate) -> SettingsRead:
        brand_id = self._resolve_brand_id(brand_id, required=True)
        brand = await self._get_brand(brand_id)
        model = await self._get_or_create(brand_id)
        values = data.model_dump()
        new_currencies = values.pop("currencies")
        new_name, new_code = values.pop("brand_name"), values.pop("brand_code")
        if new_currencies is not None:
            await self._validate_currencies(brand_id, new_currencies)
            model.currencies = new_currencies
        if new_name:
            brand.name = new_name
        if new_code and new_code != brand.code:
            taken = (await self.db.execute(
                select(BrandModel.id).where(BrandModel.code == new_code, BrandModel.id != brand_id)
            )).first()
            if taken:
                raise ConflictException("Ya existe una marca con ese código")
            brand.code = new_code
        for field, value in values.items():
            setattr(model, field, value)
        await self.db.commit()
        await self.db.refresh(model)
        await self.db.refresh(brand)
        return self._to_read(brand, model)

    async def _validate_currencies(self, brand_id: UUID, currencies: list[str]) -> None:
        if not currencies:
            raise AppException("Elige al menos una moneda", status_code=400)
        invalid = [code for code in currencies if not is_valid(code)]
        if invalid:
            raise AppException(f"Monedas no válidas: {', '.join(invalid)}", status_code=400)
        in_use = {row[0] for row in (await self.db.execute(select(RouteModel.currency).where(RouteModel.brand_id == brand_id).distinct())).all()}
        removed = sorted(in_use - set(currencies))
        if removed:
            raise ConflictException(f"No puedes quitar {', '.join(removed)}: hay rutas que la usan")

    @staticmethod
    def _variant_fields(variant: LogoVariant) -> tuple[str, str, str, str]:
        """(campo_blob, campo_width, campo_height, campo_tone) de la ranura full o mark."""
        if variant not in _LOGO_VARIANTS:
            raise AppException("Ranura de logo inválida: usa 'full' o 'mark'", status_code=400)
        return f"logo_{variant}_blob", f"logo_{variant}_width", f"logo_{variant}_height", f"logo_{variant}_tone"

    async def upload_logo(self, brand_id: Optional[UUID], variant: LogoVariant, data: bytes) -> SettingsRead:
        brand_id = self._resolve_brand_id(brand_id, required=True)
        blob_field, width_field, height_field, tone_field = self._variant_fields(variant)
        if not self.storage.is_configured:
            from app.infrastructure.storage.azure_blob import StorageNotConfigured
            raise StorageNotConfigured()
        if not data:
            raise AppException("El archivo está vacío", status_code=400)
        if len(data) > MAX_LOGO_BYTES:
            raise AppException("El logo debe pesar menos de 5 MB", status_code=413)
        detected = detect_image(data)
        if not detected:
            raise AppException("Formato no permitido: usa PNG, JPG, WEBP o SVG", status_code=415)
        content_type, _ = detected

        normalized = normalize_logo(data, content_type)
        if normalized is None:
            raise AppException("No se pudo procesar la imagen", status_code=415)

        brand = await self._get_brand(brand_id)
        model = await self._get_or_create(brand_id)
        old_blob = getattr(model, blob_field)
        new_blob = f"brands/{brand_id}/logo-{variant}-{uuid.uuid4().hex[:8]}.{normalized.ext}"

        await self.storage.upload(new_blob, normalized.data, normalized.content_type)
        setattr(model, blob_field, new_blob)
        setattr(model, width_field, normalized.width)
        setattr(model, height_field, normalized.height)
        setattr(model, tone_field, normalized.tone)
        await self.db.commit()
        await self.db.refresh(model)
        if old_blob:
            await self.storage.delete(old_blob)
        return self._to_read(brand, model)

    async def delete_logo(self, brand_id: Optional[UUID], variant: LogoVariant) -> SettingsRead:
        brand_id = self._resolve_brand_id(brand_id, required=True)
        blob_field, width_field, height_field, tone_field = self._variant_fields(variant)
        brand = await self._get_brand(brand_id)
        model = await self._get_or_create(brand_id)
        old_blob = getattr(model, blob_field)
        setattr(model, blob_field, None)
        setattr(model, width_field, None)
        setattr(model, height_field, None)
        setattr(model, tone_field, None)
        await self.db.commit()
        await self.db.refresh(model)
        if old_blob:
            await self.storage.delete(old_blob)
        return self._to_read(brand, model)
