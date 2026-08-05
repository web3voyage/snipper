"""Remote one-time activation service for StealthOverlay."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, String, create_engine, select, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


PRODUCT_ID = "stealthoverlay"
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 12


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def normalize_code(value: str) -> str:
    return "".join(character for character in value.upper() if character.isalnum())


def generate_code() -> str:
    while True:
        value = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if any(character.isalpha() for character in value) and any(
            character.isdigit() for character in value
        ):
            return value


def code_digest(value: str) -> str:
    pepper = os.environ.get("LICENSE_CODE_PEPPER", "").encode("utf-8")
    if len(pepper) < 24:
        raise RuntimeError("LICENSE_CODE_PEPPER must contain at least 24 characters.")
    return hmac.new(pepper, normalize_code(value).encode("ascii"), hashlib.sha256).hexdigest()


def private_key() -> Ed25519PrivateKey:
    path = Path(os.environ.get("LICENSE_PRIVATE_KEY_FILE", "private_key.pem"))
    try:
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    except (OSError, ValueError, TypeError) as exc:
        raise RuntimeError("LICENSE_PRIVATE_KEY_FILE is missing or invalid.") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise RuntimeError("The license signing key must be Ed25519.")
    return key


def issue_token(license_id: str, installation_id: str) -> str:
    payload = {
        "schema": 1,
        "product": PRODUCT_ID,
        "license_id": license_id,
        "installation_id": installation_id,
        "issued_at": utc_now().isoformat(),
    }
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{base64url(payload_bytes)}.{base64url(private_key().sign(payload_bytes))}"


class Base(DeclarativeBase):
    pass


class LicenseKey(Base):
    __tablename__ = "license_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    product: Mapped[str] = mapped_column(String(64), index=True)
    code_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    installation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    activation_token: Mapped[str | None] = mapped_column(String(1024), nullable=True)


database_url = os.environ.get("LICENSE_DATABASE_URL", "sqlite:///./licenses.db")
engine_options = {"connect_args": {"check_same_thread": False}} if database_url.startswith("sqlite") else {}
engine = create_engine(database_url, pool_pre_ping=True, **engine_options)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
Base.metadata.create_all(engine)

app = FastAPI(title="StealthOverlay License Service", docs_url=None, redoc_url=None)


class GenerateKeysRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=500)
    valid_days: int = Field(default=30, ge=1, le=3650)


class RedeemRequest(BaseModel):
    code: str = Field(min_length=12, max_length=20)
    installation_id: uuid.UUID
    product: str
    app_version: str = Field(max_length=32)


def database_session():
    with SessionLocal() as session:
        yield session


def require_admin(x_admin_token: str = Header(default="")) -> None:
    expected = os.environ.get("LICENSE_ADMIN_TOKEN", "")
    if len(expected) < 24 or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="Invalid administrator token.")


@app.get("/health")
def health():
    return {"status": "ok", "service": "StealthOverlayLicenseService"}


@app.post("/admin/keys", dependencies=[Depends(require_admin)])
def create_keys(request: GenerateKeysRequest, session: Session = Depends(database_session)):
    expires_at = utc_now() + timedelta(days=request.valid_days)
    visible_codes: list[str] = []
    for _ in range(request.count):
        while True:
            code = generate_code()
            if not session.scalar(select(LicenseKey.id).where(LicenseKey.code_digest == code_digest(code))):
                break
        session.add(
            LicenseKey(
                id=str(uuid.uuid4()),
                product=PRODUCT_ID,
                code_digest=code_digest(code),
                created_at=utc_now(),
                expires_at=expires_at,
            )
        )
        visible_codes.append(code)
    session.commit()
    return {"codes": visible_codes, "expires_at": expires_at.isoformat()}


@app.post("/v1/activations/redeem")
def redeem(request: RedeemRequest, session: Session = Depends(database_session)):
    if request.product != PRODUCT_ID:
        raise HTTPException(status_code=400, detail="This code is for another product.")
    normalized = normalize_code(request.code)
    if len(normalized) != CODE_LENGTH or normalized.isalpha() or normalized.isdigit():
        raise HTTPException(status_code=400, detail="The activation code format is invalid.")

    digest = code_digest(normalized)
    record = session.scalar(select(LicenseKey).where(LicenseKey.code_digest == digest))
    if record is None or record.product != PRODUCT_ID:
        raise HTTPException(status_code=404, detail="The activation code is invalid.")
    installation_id = str(request.installation_id)
    if record.redeemed_at is not None:
        if record.installation_id == installation_id and record.activation_token:
            return {"activation_token": record.activation_token, "already_activated": True}
        raise HTTPException(status_code=409, detail="This activation code has already been used.")
    expiry = record.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= utc_now():
        raise HTTPException(status_code=410, detail="This activation code has expired.")

    token = issue_token(record.id, installation_id)
    redeemed_at = utc_now()
    result = session.execute(
        update(LicenseKey)
        .where(LicenseKey.id == record.id, LicenseKey.redeemed_at.is_(None))
        .values(
            redeemed_at=redeemed_at,
            installation_id=installation_id,
            activation_token=token,
        )
    )
    if result.rowcount != 1:
        session.rollback()
        winner = session.get(LicenseKey, record.id)
        if winner and winner.installation_id == installation_id and winner.activation_token:
            return {"activation_token": winner.activation_token, "already_activated": True}
        raise HTTPException(status_code=409, detail="This activation code has already been used.")
    session.commit()
    return {"activation_token": token, "already_activated": False}
