from typing import Optional

from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.security.base import SecurityBase
from fastapi.security.utils import get_authorization_scheme_param
from fastapi.openapi.models import HTTPBearer as HTTPBearerModel
from jose import JWTError, jwt

from .config import Settings

settings = Settings()


class WebSocketBearer(SecurityBase):
    def __init__(
        self,
        *,
        bearerFormat: Optional[str] = None,
        scheme_name: Optional[str] = None,
        auto_error: bool = True,
    ):
        self.model = HTTPBearerModel(bearerFormat=bearerFormat)
        self.scheme_name = scheme_name or self.__class__.__name__
        self.auto_error = auto_error

    async def __call__(
        self, websocket: WebSocket
    ) -> Optional[HTTPAuthorizationCredentials]:
        authorization: str = websocket.headers.get("Authorization")
        scheme, credentials = get_authorization_scheme_param(authorization)
        if not (authorization and scheme and credentials):
            if self.auto_error:
                await websocket.close(status.WS_1008_POLICY_VIOLATION)
            else:
                return None
        if scheme.lower() != "bearer":
            if self.auto_error:
                await websocket.close(status.WS_1008_POLICY_VIOLATION)
            else:
                return None
        return HTTPAuthorizationCredentials(scheme=scheme, credentials=credentials)


auth_scheme = HTTPBearer()
auth_scheme_ws = WebSocketBearer()


async def get_token(creds: HTTPAuthorizationCredentials = Depends(auth_scheme)) -> str:
    return creds.credentials


async def get_current_user(token: str = Depends(get_token)) -> str:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.token_key, algorithms=[settings.token_algo]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return user_id


async def get_token_ws(
    creds: HTTPAuthorizationCredentials = Depends(auth_scheme_ws),
) -> str:
    return creds.credentials


async def get_current_user_ws(
    websocket: WebSocket, token: str = Depends(get_token_ws)
) -> str:
    try:
        payload = jwt.decode(
            token, settings.token_key, algorithms=[settings.token_algo]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            await websocket.close(status.WS_1003_UNSUPPORTED_DATA)
            raise ValueError
    except JWTError:
        await websocket.close(status.WS_1003_UNSUPPORTED_DATA)
        raise ValueError
    return user_id
