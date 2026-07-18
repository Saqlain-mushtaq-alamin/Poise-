"""Generic key/value settings endpoints, backing things like the theme
toggle in Phase 1. Domain-specific settings (hardware tier, BYOK keys in
Phase 2, etc.) get their own routers rather than overloading this one."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.settings import AppSettings

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingValue(BaseModel):
    value: str | None


@router.get("/{key}", response_model=SettingValue)
def get_setting(key: str, db: DBSession = Depends(get_db)) -> SettingValue:
    row = db.get(AppSettings, key)
    return SettingValue(value=row.value if row else None)


@router.put("/{key}", response_model=SettingValue)
def put_setting(key: str, body: SettingValue, db: DBSession = Depends(get_db)) -> SettingValue:
    row = db.get(AppSettings, key)
    if row is None:
        row = AppSettings(key=key, value=body.value)
        db.add(row)
    else:
        row.value = body.value
    db.commit()
    return SettingValue(value=row.value)
