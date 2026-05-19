"""
@require_auth — reads JWT from httpOnly cookie or Authorization header.
"""
from functools import wraps
from flask import request, jsonify, g
import jwt as pyjwt
from app.auth.jwt_utils import decode_token


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({"error": "Необхідна авторизація"}), 401
        try:
            payload = decode_token(token)
        except pyjwt.ExpiredSignatureError:
            return jsonify({"error": "Сесія закінчилась — увійдіть знову"}), 401
        except pyjwt.PyJWTError:
            return jsonify({"error": "Невалідний токен"}), 401

        if payload.get("type") != "access":
            return jsonify({"error": "Невірний тип токена"}), 401

        from app.database.db import get_user_by_id
        user = get_user_by_id(payload["sub"])
        if not user or not user.get("is_active"):
            return jsonify({"error": "Користувача не знайдено"}), 401

        g.user_id = payload["sub"]
        g.user    = user
        return f(*args, **kwargs)
    return wrapper


def _extract_token() -> str | None:
    # 1. httpOnly cookie (preferred)
    token = request.cookies.get("access_token")
    if token:
        return token
    # 2. Authorization: Bearer <token>
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:]
    return None
