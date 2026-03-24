from flask import Flask, jsonify, Response, request, Blueprint
from connector import get_connection
from decorators import jwt_required
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

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


@models_bp.route('/forgot_pass',methods=['POST'])
def forgot_pass():
    try:
        conn = get_connection()
        cursor = conn.cursor()

        data = request.json
        email = data.get('email')
        new_pass = data.get('new_pass')
        en_pass = generate_password_hash(new_pass)

        cursor.execute("SELECT * FROM USERS WHERE EMAIL = %s",(email,))
        user = cursor.fetchone()
        if not user:
            return jsonify({
                'status':'fail',
                'message':'email not found'
            })
        else:
            cursor.execute("update users set password = %s where email = %s",(en_pass,email))
            conn.commit()
            return jsonify({
                'status':'success',
                'message':'Password Changed Successfully.'
            })

    except Exception as e:
        return jsonify({
            'status':'error',
            'message':str(e)
        })
    
    finally:
        cursor.close()
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

        cursor.execute("insert into contacts(id, name, email, subject, message, created_at) values(%s,%s,%s,%s,%s,NOW())",(id,name,email,sub,msg))
        conn.commit()
        return jsonify({
            'status':'success',
            'message':'Contact Request Submitted Succssfully'
        })
    except Exception as e:
        return jsonify({
            'status':'error',
            'message':str(e)
        })
  
