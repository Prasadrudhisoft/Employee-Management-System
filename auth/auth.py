from flask import Flask, Blueprint, jsonify, redirect, request
from connector import get_connection
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
from tokens import create_token


auth_bp = Blueprint('auth',__name__)

@auth_bp.route('/login',methods = ['GET', 'POST'])
def login():
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        data = request.json
        email = data.get('email')
        password = data.get('password')

        cursor.execute("SELECT * FROM USERS where email = %s and Status='Active'",(email,))
        user_mail = cursor.fetchone()
        if not user_mail:
            return jsonify({
                'status':'fail',
                'message':'Email Not Found Or Deactivated'
            })
        else:
            cursor.execute("SELECT * FROM USERS where email = %s",(email,))
            user = cursor.fetchone()
            pas = user["Password"]
            if not user or not check_password_hash(pas, password):
                return jsonify({
                    'status':'fail',
                    'message':'Invalid Password'
                })
            else:
                token_data = {
                    "id": user["id"],
                    "org_id": user["org_id"],
                    "role": user["Role"]
                }
                token = create_token(token_data)
                user_data = {
                    "id": user["id"],
                    "name": user["Name"],
                    "email": user["Email"],
                    "role": user["Role"],
                    "org_id": user["org_id"],
                    "status": user["Status"],
                    "contact": user["Contact"]
                }
                return jsonify({
                    'status': 'success',
                    'message': 'Login Succssfully.',
                    'user_data': user_data,
                    'token': token
                })

    except Exception as e:
        return jsonify({
            'status':'error',
            'message': str(e)
        })

