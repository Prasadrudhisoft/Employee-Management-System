from flask import Blueprint, jsonify, request
from connector import get_connection
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
from tokens import create_token

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        data     = request.json
        email    = data.get('email')
        password = data.get('password')

        # ── Fetch user by email only first, then check status/role in Python
        # This avoids column-name casing issues in the WHERE clause
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if not user:
            return jsonify({'status': 'fail', 'message': 'Email not found'})

        # Check status — handle both 'Status' and 'status' key casing
        status = user.get('Status') or user.get('status') or ''
        role   = user.get('Role')   or user.get('role')   or ''

        if status.lower() != 'active':
            return jsonify({'status': 'fail', 'message': 'Account is deactivated'})

        if role.lower() == 'super_admin':
            return jsonify({'status': 'fail', 'message': 'Access denied'})

        # Check password
        db_password = user.get('Password') or user.get('password') or ''
        if not check_password_hash(db_password, password):
            return jsonify({'status': 'fail', 'message': 'Invalid password'})

        token_data = {
            "id":       user.get("id"),
            "org_id":   user.get("org_id"),
            "role":     role,
            "org_name": user.get("org_name")
        }
        token = create_token(token_data)

        user_data = {
            "id":       user.get("id"),
            "name":     user.get("Name")    or user.get("name"),
            "email":    user.get("Email")   or user.get("email"),
            "role":     role,
            "org_id":   user.get("org_id"),
            "status":   status,
            "contact":  user.get("Contact") or user.get("contact"),
            "org_name": user.get("org_name")
        }

        return jsonify({
            'status':    'success',
            'message':   'Login successfully.',
            'user_data': user_data,
            'token':     token
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

    finally:
        if cursor: cursor.close()
        if conn:   conn.close()