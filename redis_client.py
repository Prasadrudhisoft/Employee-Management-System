# redis_client.py
import redis
import json
import time
import os
import base64

# ADD THIS: Load .env file if running as standalone script
from dotenv import load_dotenv
load_dotenv()

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_DB = int(os.environ.get('REDIS_DB', 0))
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)

# Create Redis connection pool
redis_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD if REDIS_PASSWORD else None,
    decode_responses=True,
    max_connections=20,
    # ADD THESE TWO TIMEOUTS for production
    socket_timeout=5,           # Prevents hanging connections
    socket_connect_timeout=5    # Quick fail if Redis is down
)

redis_client = redis.Redis(connection_pool=redis_pool)

def test_redis_connection():
    """Test if Redis is working"""
    try:
        redis_client.ping()
        print("✅ Redis connection successful!")
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

def encode_bytes_to_base64(data):
    """Convert bytes to base64 string for Redis storage"""
    if data is None:
        return None
    if isinstance(data, bytes):
        return base64.b64encode(data).decode('utf-8')
    return data

def decode_base64_to_bytes(data):
    """Convert base64 string back to bytes"""
    if data is None:
        return None
    if isinstance(data, str):
        try:
            return base64.b64decode(data)
        except:
            return data
    return data

def store_otp(flow, email, otp_data):
    """Store OTP in Redis with 5 minutes expiry"""
    key = f"otp:{flow}:{email}"
    # ADD TRY-CATCH for production
    try:
        redis_client.setex(
            key, 
            300,  # 5 minutes expiry
            json.dumps(otp_data)
        )
        return True
    except Exception as e:
        print(f"Error storing OTP: {e}")
        return False

def get_otp(flow, email):
    """Retrieve OTP from Redis"""
    key = f"otp:{flow}:{email}"
    # ADD TRY-CATCH for production
    try:
        data = redis_client.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        print(f"Error getting OTP: {e}")
        return None

def delete_otp(flow, email):
    """Delete OTP from Redis"""
    key = f"otp:{flow}:{email}"
    # ADD TRY-CATCH for production
    try:
        redis_client.delete(key)
        return True
    except Exception as e:
        print(f"Error deleting OTP: {e}")
        return False

def store_pending_data(email, data):
    """Store pending registration data in Redis with 1 hour expiry"""
    key = f"pending:{email}"
    
    # Create a copy of the data to avoid modifying original
    serializable_data = {}
    
    for k, v in data.items():
        # Handle binary image data
        if k == 'profile_img_bytes' and v is not None:
            serializable_data[k] = encode_bytes_to_base64(v)
        else:
            serializable_data[k] = v
    
    # Convert to JSON-serializable format
    try:
        json_data = json.dumps(serializable_data, default=str)
        redis_client.setex(key, 3600, json_data)
        return True
    except Exception as e:
        print(f"Error storing pending data: {e}")
        return False

def get_pending_data(email):
    """Retrieve pending data from Redis"""
    key = f"pending:{email}"
    try:
        data = redis_client.get(key)
        if data:
            pending_data = json.loads(data)
            # Convert base64 image data back to bytes
            if pending_data.get('profile_img_bytes'):
                pending_data['profile_img_bytes'] = decode_base64_to_bytes(
                    pending_data['profile_img_bytes']
                )
            return pending_data
        return None
    except Exception as e:
        print(f"Error retrieving pending data: {e}")
        return None

def delete_pending_data(email):
    """Delete pending data from Redis"""
    key = f"pending:{email}"
    try:
        redis_client.delete(key)
        return True
    except Exception as e:
        print(f"Error deleting pending data: {e}")
        return False

def store_reset_token(email, token):
    """Store password reset token in Redis with 10 minutes expiry"""
    key = f"reset_token:{email}"
    try:
        redis_client.setex(key, 600, token)
        return True
    except Exception as e:
        print(f"Error storing reset token: {e}")
        return False

def get_reset_token(email):
    """Get password reset token from Redis"""
    key = f"reset_token:{email}"
    try:
        return redis_client.get(key)
    except Exception as e:
        print(f"Error getting reset token: {e}")
        return None

def delete_reset_token(email):
    """Delete reset token from Redis"""
    key = f"reset_token:{email}"
    try:
        redis_client.delete(key)
        return True
    except Exception as e:
        print(f"Error deleting reset token: {e}")
        return False

# Test connection when module loads
test_redis_connection()