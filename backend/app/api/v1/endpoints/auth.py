from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr, Field
from typing import Dict, Any, Optional
from app.services.user_service import UserService
from app.core.security import create_access_token, get_current_user_from_token

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5, max_length=100)
    password: str = Field(..., min_length=6, max_length=100)


class LoginRequest(BaseModel):
    username_or_email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    try:
        user = UserService.register_user(
            username=req.username.strip(),
            email=req.email.strip().lower(),
            password=req.password
        )
        token = create_access_token(data={
            "sub": user["id"],
            "username": user["username"],
            "email": user["email"]
        })
        return AuthResponse(access_token=token, user=user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Registration failed: {str(e)}")


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    user = UserService.authenticate_user(
        username_or_email=req.username_or_email.strip(),
        password=req.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password."
        )
    
    token = create_access_token(data={
        "sub": user["id"],
        "username": user["username"],
        "email": user["email"]
    })
    return AuthResponse(access_token=token, user=user)


@router.get("/me")
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user_from_token)):
    user = UserService.get_user_by_id(current_user["user_id"])
    if not user:
        return current_user
    return user
