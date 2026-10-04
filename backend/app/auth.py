from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlmodel import Session, select

from app.config import settings
from app.database import get_session
from app.models import AgentToken, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    expire = datetime.utcnow() + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar la credencial",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    # Dos tipos de credencial válida acá:
    # 1. El JWT de corta duración que usa el panel web (login con email/contraseña).
    # 2. El token de larga duración del agente local (ver app/routers/agent.py),
    #    reconocible por el prefijo "agt_" -- así el mismo agente puede llamar a
    #    cualquier endpoint protegido (cámaras, zonas, licencia) sin tener que
    #    loguearse con la contraseña cada vez ni guardarla en disco.
    if token.startswith("agt_"):
        agent_token = session.exec(select(AgentToken).where(AgentToken.token == token)).first()
        if agent_token is None:
            raise credentials_exception
        user = session.get(User, agent_token.user_id)
        if user is None:
            raise credentials_exception
        agent_token.last_seen_at = datetime.now(timezone.utc)
        if request is not None and request.client is not None:
            agent_token.last_seen_ip = request.client.host
        session.add(agent_token)
        session.commit()
        return user

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_user_from_query_or_header(
    request: Request, session: Session = Depends(get_session)
) -> User:
    """Para el <img>/MJPEG del navegador, que no puede mandar headers Authorization.
    Acepta ?token=... en la URL además del header Bearer habitual."""
    token = request.query_params.get("token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ")
    if not token:
        raise HTTPException(status_code=401, detail="Falta token")
    return get_current_user(request=request, token=token, session=session)
