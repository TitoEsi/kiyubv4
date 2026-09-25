"""Auth for workflow users. Memory tests use HS256; production uses Supabase JWT."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from .db import get_db, supabase_enabled
from .models import User
from .permissions import Actor
from .repositories.base import MemoryStore

JWT_SECRET = os.environ.get("JWT_SECRET", "kiyub-dev-jwt-secret-change-me")
JWT_ALG = "HS256"
JWT_HOURS = int(os.environ.get("JWT_HOURS", "72"))
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"pbkdf2${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt, digest = stored.split("$", 2)
    except ValueError:
        return False
    if scheme != "pbkdf2":
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return hmac.compare_digest(dk.hex(), digest)


def create_token(user: User) -> str:
    payload = {
        "sub": user.id,
        "role": user.role,
        "email": user.email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])


def issue_session_token(user: User, password: str | None = None) -> str:
    if supabase_enabled() and password:
        from supabase.auth import sign_in_password

        token, _uid = sign_in_password(user.email, password)
        return token
    return create_token(user)


def provision_user(db: MemoryStore, email: str, password: str, role: str, approved: bool, user_id: str | None = None) -> User:
    """Create a profile. Passwords live in Supabase Auth in production."""
    if supabase_enabled():
        from supabase.auth import admin_create_user, admin_user_id_by_email

        try:
            uid = admin_create_user(email, password, role, approved, user_id=user_id)
        except HTTPException as exc:
            if exc.status_code != 409:
                raise
            uid = user_id or admin_user_id_by_email(email)
            if not uid:
                raise
        user = db.get(User, uid)
        if user is None:
            user = User(id=uid, email=email, role=role, approved=approved, password_hash="")
            db.add(user)
            db.flush()
        else:
            user.email = email
            user.role = role
            user.approved = approved
        return user
    user = User(email=email, password_hash=hash_password(password), role=role, approved=approved)
    if user_id:
        user.id = user_id
    db.add(user)
    db.flush()
    return user


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: MemoryStore = Depends(get_db),
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = creds.credentials
    if supabase_enabled():
        from supabase.auth import verify_supabase_jwt

        user_id = verify_supabase_jwt(token)
    else:
        try:
            payload = decode_token(token)
        except JWTError:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
        user_id = payload.get("sub")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    blocked = account_block_reason(user)
    if blocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, blocked)
    return user


def account_block_reason(user: User) -> str | None:
    if getattr(user, "deleted_at", None):
        return "Account is no longer available"
    if getattr(user, "suspended", False):
        return "Account is suspended"
    if user.role == "ARCHITECT" and not user.approved:
        return "Architect account pending IT approval"
    return None


def actor_from(user: User) -> Actor:
    return Actor(
        id=user.id,
        role=user.role,
        approved=user.approved,
        suspended=bool(getattr(user, "suspended", False)),
    )
