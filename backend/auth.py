import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional

import jwt
from flask import g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from backend.config import COOKIE_NAME, JWT_EXP_DAYS, SECRET_KEY
from backend.db import get_db, row_to_dict


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    return check_password_hash(password_hash, password)


def make_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(days=JWT_EXP_DAYS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None


def current_user():
    return getattr(g, "user", None)


def get_user_by_id(user_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, name, email, phone, plan, theme, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return row_to_dict(row)


def load_user_from_request():
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            token = header[7:]
    if not token:
        g.user = None
        return
    user_id = decode_token(token)
    g.user = get_user_by_id(user_id) if user_id else None


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return jsonify({"error": "Não autenticado."}), 401
        return fn(*args, **kwargs)

    return wrapper


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_reset_token() -> str:
    return secrets.token_urlsafe(32)


def tokens_match(provided: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_reset_token(provided), stored_hash)
