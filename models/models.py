import random
import time
import os
import requests
import uuid
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash
from connector import get_connection
from decorators import jwt_required
import pymysql

models_bp = Blueprint('models', __name__)

# ------------------ ZeptoMail Configuration ------------------
ZEPTOMAIL_API_URL = "https://api.zeptomail.in/v1.1/email"
ZEPTOMAIL_API_TOKEN = os.environ.get("ZEPTO_TOKEN")
ZEPTOMAIL_FROM_EMAIL = "contact@rudhisoft.com"
ZEPTOMAIL_FROM_NAME = "StaffCores"

# ------------------ In‑memory stores (same as civil project) ------------------
otp_store = {}          # email -> {'otp': '123456', 'expires_at': timestamp}
pending_data = {}       # email -> registration data dict
reset_token_store = {}  # email -> reset_token (for password reset)

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp_email(email, otp):
    """Send OTP email using ZeptoMail. Returns (success, error_msg)"""
    if not ZEPTOMAIL_API_TOKEN:
        print("ZeptoMail API token not set in environment variables.")
        return False, "ZEPTO_TOKEN environment variable not set"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Zoho-enczapikey {ZEPTOMAIL_API_TOKEN}"
    }

    payload = {
            "from": {
                "address": ZEPTOMAIL_FROM_EMAIL,
                "name": ZEPTOMAIL_FROM_NAME
            },
            "to": [
                {
                    "email_address": {
                        "address": email
                    }
                }
            ],
            "subject": "Your OTP Code for Verification",
            "htmlbody": f"""
                <html>
                    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                            <h2 style="color: #1e3a8a; text-align: center;">OTP Verification</h2>
                            <p>Hello,</p>
                            <p>Your One-Time Password (OTP) for verification is:</p>
                            <div style="text-align: center; margin: 30px 0;">
                                <span style="font-size: 32px; font-weight: bold; color: #1e3a8a; letter-spacing: 5px; padding: 15px 30px; border: 2px dashed #1e3a8a; border-radius: 8px; display: inline-block;">
                                    {otp}
                                </span>
                            </div>
                            <p style="color: #e74c3c; font-weight: bold;">⚠️ This code will expire in 5 minutes.</p>
                            <p>If you didn't request this code, please ignore this email.</p>
                            <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                            <p style="font-size: 12px; color: #666;">
                                Best regards,<br>
                                <strong>StaffCores Team</strong>
                            </p>
                        </div>
                    </body>
                </html>
            """
        }

    try:
        response = requests.post(ZEPTOMAIL_API_URL, headers=headers, json=payload, timeout=10)
        print(f"ZeptoMail Status: {response.status_code}")
        print(f"ZeptoMail Response: {response.text}")

        if response.status_code in (200,201,202):
            return True, None
        else:
            return False, f"API returned {response.status_code}: {response.text}"
    except Exception as e:
        return False, str(e)

# ===================== REGISTRATION OTP (Civil Project Pattern) =====================

@models_bp.route('/register_request', methods=['POST'])
def register_request():
    """
    Step 1: Collect user data, send OTP, store pending data.
    Expected JSON: { "name": "", "email": "", "password": "", "role": "", ... }
    """
    data = request.json
    email = data.get('email')
    if not email:
        return jsonify({'status': 'fail', 'message': 'Email is required'}), 400

    # Check if email already exists
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'status': 'fail', 'message': 'Email already registered'}), 409
    cursor.close()
    conn.close()

    # Store pending registration data (exactly like civil project)
    pending_data[email] = {
        'name': data.get('name'),
        'email': email,
        'password': data.get('password'),     # plain text, will be hashed later
        'role': data.get('role', 'user'),
        'contact': data.get('contact'),
        'address': data.get('address'),
        'department_id': data.get('department_id'),
        'designation': data.get('designation'),
        'join_date': data.get('join_date'),
        'profile_img': None,   # handle file upload separately if needed
        # add any other fields your users table needs
    }

    otp = generate_otp()
    otp_store[email] = {'otp': otp, 'expires_at': time.time() + 300}

    success, error = send_otp_email(email, otp)
    if not success:
        otp_store.pop(email, None)
        pending_data.pop(email, None)
        return jsonify({'status': 'error', 'message': f'Failed to send OTP: {error}'}), 500

    return jsonify({
        'status': 'success',
        'message': 'OTP sent to your email. Please verify to complete registration.',
        'pending_id': email
    })

@models_bp.route('/register_verify', methods=['POST'])
def register_verify():
    """
    Step 2: Verify OTP and create user in database.
    Expected JSON: { "email": "", "otp": "" }
    """
    data = request.json
    email = data.get('email')
    otp = data.get('otp')

    if not email or not otp:
        return jsonify({'status': 'fail', 'message': 'Email and OTP are required'}), 400

    stored = otp_store.get(email)
    if not stored or time.time() > stored['expires_at']:
        return jsonify({'status': 'fail', 'message': 'OTP expired or not requested'}), 400
    if stored['otp'] != otp:
        return jsonify({'status': 'fail', 'message': 'Invalid OTP'}), 400

    # Retrieve and remove pending data
    pending = pending_data.pop(email, None)
    otp_store.pop(email, None)
    if not pending:
        return jsonify({'status': 'fail', 'message': 'No pending registration for this email'}), 400

    # Create user in database
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        user_id = str(uuid.uuid4())
        hashed_pw = generate_password_hash(pending['password'])

        # Adjust table and column names according to your schema (here using 'users' table)
        cursor.execute("""
            INSERT INTO users (id, name, email, password, role, contact, address, department_id, designation, join_date, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (user_id, pending['name'], email, hashed_pw, pending['role'],
              pending.get('contact'), pending.get('address'), pending.get('department_id'),
              pending.get('designation'), pending.get('join_date')))
        conn.commit()
        return jsonify({'status': 'success', 'message': 'User registered successfully'})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ===================== PASSWORD RESET OTP (Fixed with token validation) =====================

@models_bp.route('/send_otp', methods=['POST'])
def send_otp():
    data = request.json
    email = data.get('email')
    if not email:
        return jsonify({'status': 'fail', 'message': 'Email is required'}), 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        return jsonify({'status': 'fail', 'message': 'Email not registered'}), 404

    otp = generate_otp()
    otp_store[email] = {'otp': otp, 'expires_at': time.time() + 300}

    success, error = send_otp_email(email, otp)
    if success:
        return jsonify({'status': 'success', 'message': 'OTP sent to your email'})
    else:
        otp_store.pop(email, None)
        return jsonify({'status': 'error', 'message': error}), 500

@models_bp.route('/verify_otp', methods=['POST'])
def verify_otp():
    data = request.json
    email = data.get('email')
    otp = data.get('otp')

    if not email or not otp:
        return jsonify({'status': 'fail', 'message': 'Email and OTP are required'}), 400

    stored = otp_store.get(email)
    if not stored or time.time() > stored['expires_at']:
        return jsonify({'status': 'fail', 'message': 'OTP expired or not requested'}), 400
    if stored['otp'] != otp:
        return jsonify({'status': 'fail', 'message': 'Invalid OTP'}), 400

    # OTP is valid – generate a reset token and store it
    reset_token = str(uuid.uuid4())
    reset_token_store[email] = reset_token
    # Remove OTP store entry (optional, but good practice)
    del otp_store[email]

    return jsonify({
        'status': 'success',
        'message': 'OTP verified',
        'reset_token': reset_token
    })

@models_bp.route('/reset_password', methods=['POST'])
def reset_password():
    data = request.json
    email = data.get('email')
    new_pass = data.get('new_pass')
    reset_token = data.get('reset_token')

    if not email or not new_pass or not reset_token:
        return jsonify({'status': 'fail', 'message': 'Email, new password and reset token required'}), 400

    # Validate reset token
    stored_token = reset_token_store.get(email)
    if not stored_token or stored_token != reset_token:
        return jsonify({'status': 'fail', 'message': 'Invalid or missing reset token'}), 401

    # Update password
    en_pass = generate_password_hash(new_pass)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password = %s WHERE email = %s", (en_pass, email))
    conn.commit()
    cursor.close()
    conn.close()

    # Clean up token
    reset_token_store.pop(email, None)

    return jsonify({'status': 'success', 'message': 'Password changed successfully'})

# ===================== Existing Endpoints (unchanged) =====================

@models_bp.route('/my_profile', methods=['GET'])
@jwt_required
def my_profile(id=None, org_id=None, role=None, org_name=None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("""
            SELECT u.id, u.name, u.email, u.role, u.status, u.contact,
                   u.profile_img, u.org_id, u.org_name,
                   e.designation, e.department_id, e.address, e.join_date
            FROM users u
            LEFT JOIN emp_detailes e ON e.user_id = u.id
            WHERE u.id = %s
        """, (id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({'status': 'error', 'message': 'User not found'})
        base_url = request.host_url.rstrip('/')
        user['profile_img_url'] = f"{base_url}/{user['profile_img']}" if user.get('profile_img') else None
        user.pop('profile_img', None)
        return jsonify({'status': 'success', 'data': user})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@models_bp.route('/forgot_pass', methods=['POST'])
def forgot_pass():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        data = request.json
        email = data.get('email')
        new_pass = data.get('new_pass')
        en_pass = generate_password_hash(new_pass)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if not user:
            return jsonify({'status': 'fail', 'message': 'email not found'})
        cursor.execute("UPDATE users SET password = %s WHERE email = %s", (en_pass, email))
        conn.commit()
        return jsonify({'status': 'success', 'message': 'Password Changed Successfully.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@models_bp.route('/contact_us', methods=['POST'])
def contact_us():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        data = request.json
        id = str(uuid.uuid4())
        name = data.get("name")
        email = data.get("email")
        sub = data.get("sub")
        msg = data.get("msg")
        cursor.execute("INSERT INTO contacts(id, name, email, subject, message, created_at) VALUES(%s,%s,%s,%s,%s,NOW())", (id,name,email,sub,msg))
        conn.commit()
        return jsonify({'status':'success','message':'Contact Request Submitted Successfully'})
    except Exception as e:
        return jsonify({'status':'error','message':str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()