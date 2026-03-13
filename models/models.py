from flask import Flask, jsonify, Response, request, Blueprint
from connector import get_connection
from decorators import jwt_required
import pymysql

models_bp = Blueprint('models',__name__)


from flask import request

@models_bp.route('/my_profile', methods=['GET'])
@jwt_required
def my_profile(id=None, org_id=None, role=None, org_name=None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        cursor.execute("""
            SELECT 
                u.id, u.name, u.email, u.role, u.status, u.contact,
                u.profile_img, u.org_id, u.org_name,
                e.designation, e.department_id, e.address, e.join_date
            FROM users u
            LEFT JOIN emp_detailes e ON e.user_id = u.id
            WHERE u.id = %s
        """, (id,))

        user = cursor.fetchone()

        if not user:
            return jsonify({'status': 'error', 'message': 'User not found'})

        # Build full image URL
        base_url = request.host_url.rstrip('/')
        if user.get('profile_img'):
            user['profile_img_url'] = f"{base_url}/{user['profile_img']}"
        else:
            user['profile_img_url'] = None

        # Remove raw path, frontend only needs the full URL
        user.pop('profile_img', None)

        return jsonify({'status': 'success', 'data': user})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

