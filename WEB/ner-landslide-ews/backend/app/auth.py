from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from .settings import settings

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/token")
ROLE_HIERARCHY = {"viewer":0,"resident":1,"field_officer":2,"district_admin":3,"state_admin":4}

def create_token(sub: str, role: str, district_id: Optional[int]) -> str:
    return jwt.encode({
        "sub": sub, "role": role, "district_id": district_id,
        "exp": datetime.utcnow() + timedelta(hours=12),
    }, settings.jwt_secret, algorithm=settings.jwt_alg)

def get_current_user(token: str = Depends(oauth2)) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

def require_role(min_role: str):
    def checker(user=Depends(get_current_user)):
        if ROLE_HIERARCHY[user["role"]] < ROLE_HIERARCHY[min_role]:
            raise HTTPException(403, "Insufficient role")
        return user
    return checker