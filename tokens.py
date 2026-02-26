import jwt
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = "d499fc94c6f320d3bfef78671fa9e9b4bbb6c82b93eda7b45c70ee425501fd2d251353cf209a3d9e78f3712d9170aaf93d48ef1f51d2e6ad262ee2e81b958d44"

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