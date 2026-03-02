from jose import jwt
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

ALGORITHM = "HS256"


def create_token(data: dict, expires_minutes: int = 480):
    """
    Generate JWT Token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        os.environ.get("JWT_SECRET_KEY"),
        algorithm=ALGORITHM
    )

    return encoded_jwt