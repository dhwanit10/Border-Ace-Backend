from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.core.config import settings
from passlib.context import CryptContext

# Change this later and preferably move it to .env
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM

ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


security_scheme = HTTPBearer()



pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

# =====================================
# HASH PASSWORD
# =====================================

def hash_password(password: str):

    return pwd_context.hash(password)



# ==========================================
# CREATE JWT ACCESS TOKEN
# ==========================================

def create_access_token(data: dict):

    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({
        "exp": expire
    })

    encoded_jwt = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return encoded_jwt


# ==========================================
# VERIFY JWT TOKEN
# ==========================================

def verify_access_token(
    credentials: HTTPAuthorizationCredentials
):

    token = credentials.credentials

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        return payload

    except JWTError:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )