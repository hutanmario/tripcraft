from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from app.database import get_db
from app.models.user import User
from app.config import settings


# Schema OAuth2 — FastAPI o folosește pentru a citi headerul Authorization
# tokenUrl arată unde se obține tokenul (informativ, pentru Swagger UI)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    '''
    Decodează tokenul JWT, extrage emailul, încarcă userul din DB.
    Folosit ca dependency în endpoint-uri protejate.

    Raises 401 dacă tokenul e invalid, expirat, sau userul nu există.
    '''
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Token invalid sau expirat',
        headers={'WWW-Authenticate': 'Bearer'},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        email: str = payload.get('sub')
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception

    return user