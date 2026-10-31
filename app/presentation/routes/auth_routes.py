from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.infrastructure.dababase.db import get_db
from app.infrastructure.models.brand_model import BrandModel
from app.infrastructure.models.user_model import UserModel
from app.infrastructure.utils.require_authentication import get_current_user

router = APIRouter()


def _type_user_code(user: UserModel) -> str:
    if hasattr(user.type_user, "value"):
        return user.type_user.value
    return str(user.type_user)


class VerifyBrandCodeRequest(BaseModel):
    code: str


@router.get("/me")
async def me(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    brand_name = None
    if current_user.brand_id:
        result = await db.execute(select(BrandModel).where(BrandModel.id == current_user.brand_id))
        brand = result.scalars().first()
        brand_name = brand.name if brand else None

    return {
        "id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "type_user": _type_user_code(current_user),
        "document_id": current_user.document_id,
        "brand_id": str(current_user.brand_id) if current_user.brand_id else None,
        "brand_name": brand_name,
        "clerk_user_id": current_user.clerk_user_id,
        "active": current_user.active,
    }


@router.post("/verify-brand-code")
async def verify_brand_code(
    payload: VerifyBrandCodeRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.brand_id:
        # dev users (no brand) are exempt
        return {"verified": True}

    result = await db.execute(select(BrandModel).where(BrandModel.id == current_user.brand_id))
    brand = result.scalars().first()
    if not brand or brand.code != payload.code:
        raise HTTPException(status_code=403, detail="Código de marca incorrecto")
    return {"verified": True}
