import jwt
import os
from functools import wraps
from flask import request, jsonify


ALGORITHM = "HS256"


def jwt_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):

        auth_header = request.headers.get("Authorization", "")

        if not auth_header:
            return jsonify({"message": "Token missing"}), 401

        token = auth_header.replace("Bearer ", "")

        try:
            payload = jwt.decode(
                token,
                os.environ.get("JWT_SECRET_KEY"),
                algorithms=[ALGORITHM]
            )

        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token expired"}), 401

        except jwt.InvalidTokenError:
            return jsonify({"message": "Invalid token"}), 401

        # Inject values like your FastAPI version
        kwargs["id"] = str(payload.get("id"))
        kwargs["role"] = payload.get("role")
        kwargs["org_id"] = payload.get("org_id")

        return func(*args, **kwargs)

    return wrapper