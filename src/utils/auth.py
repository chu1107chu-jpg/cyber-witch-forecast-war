"""JWT-верификация и admin-secret проверка."""
import os
from fastapi import HTTPException
from jose import jwt, JWTError


def verify_jwt(token: str) -> dict:
    secret = os.environ.get("SUPABASE_ANON_KEY", "")
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"],
                             options={"verify_aud": False})
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


def check_admin(secret: str):
    admin_secret = os.environ.get("ADMIN_SECRET", "")
    if not admin_secret or secret != admin_secret:
        raise HTTPException(status_code=403, detail="Admin access denied")
