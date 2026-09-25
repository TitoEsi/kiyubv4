"""Validate Supabase Auth JWTs and provision users via the Admin API."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

from fastapi import HTTPException, status
from jose import JWTError, jwt

from .client import get_anon_client, get_service_client, supabase_configured


def verify_supabase_jwt(token: str) -> str:
    """Return auth.users.id (`sub`) for a valid access token."""
    secret = os.environ.get("SUPABASE_JWT_SECRET", "").strip()
    if secret:
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"verify_aud": False},
            )
        except JWTError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
        return str(sub)
    try:
        result = get_anon_client().auth.get_user(token)
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc
    user = getattr(result, "user", None)
    if user is None or not getattr(user, "id", None):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    return str(user.id)


def sign_in_password(email: str, password: str) -> tuple[str, str]:
    """Return (access_token, user_id) from Supabase Auth."""
    try:
        result = get_anon_client().auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password") from exc
    session = getattr(result, "session", None)
    user = getattr(result, "user", None)
    if session is None or user is None or not session.access_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return session.access_token, str(user.id)


def admin_create_user(email: str, password: str, role: str, approved: bool, user_id: str | None = None) -> str:
    """Create an Auth user. Profile row is created by the auth.users trigger."""
    payload: dict[str, Any] = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": {"role": role, "approved": approved},
    }
    if user_id:
        payload["id"] = user_id
    try:
        result = get_service_client().auth.admin.create_user(payload)
    except Exception as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Could not create auth user: {exc}") from exc
    user = getattr(result, "user", None)
    if user is None or not getattr(user, "id", None):
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Auth user create returned no id")
    return str(user.id)


def auth_user_exists(email: str) -> bool:
    return admin_user_id_by_email(email) is not None


def invite_user_by_email(email: str, redirect_to: str, metadata: dict[str, Any] | None = None) -> str | None:
    """Send a Supabase Auth invite. Returns the Auth user id when available."""
    if not supabase_configured():
        return None
    payload: dict[str, Any] = {
        "redirect_to": redirect_to,
        "data": metadata or {},
    }
    try:
        result = get_service_client().auth.admin.invite_user_by_email(email, payload)
    except Exception as exc:
        logger.warning("invite_user_by_email failed for configured project")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Unable to send invitation. Please try again.") from exc
    user = getattr(result, "user", None)
    if user is not None and getattr(user, "id", None):
        return str(user.id)
    return None


def admin_update_password(user_id: str, password: str) -> None:
    if not supabase_configured():
        return
    try:
        get_service_client().auth.admin.update_user_by_id(user_id, {"password": password})
    except Exception as exc:
        logger.warning("admin_update_password failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Unable to activate account. Please try again.") from exc


def admin_user_id_by_email(email: str) -> str | None:
    if not supabase_configured():
        return None
    client = get_service_client()
    try:
        page = 1
        while True:
            result = client.auth.admin.list_users(page=page, per_page=200)
            users = getattr(result, "users", None) or result
            if not users:
                return None
            for user in users:
                if str(getattr(user, "email", "")).lower() == email.lower():
                    return str(user.id)
            if len(list(users)) < 200:
                return None
            page += 1
    except Exception:
        return None


def parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
