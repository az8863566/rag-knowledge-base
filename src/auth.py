"""JWT 认证工具"""

from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import config
from logger import logger

# JWT 配置
SECRET_KEY = config.api_secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = config.auth_token_expire_hours

# HTTP Bearer 认证方案
security = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建 JWT 访问令牌
    
    Args:
        data: 要编码的数据
        expires_delta: 过期时间增量
        
    Returns:
        JWT 令牌字符串
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    验证 JWT 令牌
    
    Args:
        token: JWT 令牌字符串
        
    Returns:
        解码后的数据，如果验证失败返回 None
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        
        if username is None:
            return None
        
        return payload
    except JWTError as e:
        logger.debug(f"Token 验证失败: {e}")
        return None


def get_current_user(credentials: HTTPAuthorizationCredentials) -> str:
    """
    获取当前用户（从 JWT 令牌中）
    
    Args:
        credentials: HTTP 认证凭证
        
    Returns:
        用户名
        
    Raises:
        HTTPException: 认证失败时抛出
    """
    token = credentials.credentials
    payload = verify_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    username: str = payload.get("sub")
    
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return username


class AuthError(Exception):
    """认证错误异常"""
    pass
