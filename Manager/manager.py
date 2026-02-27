from flask import request, jsonify, Blueprint
from jose import jwt
from connector import get_connection
import pymysql
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from decorators import jwt_required

manager_bp = Blueprint('manager',__name__)

@manager_bp.route('/add_emp', methods=['GET','POST'])
@jwt_required
def add_emp(id = None, org_id = None, role = None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        data = request.json
        user_id = str(uuid.uuid4())
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        roles = "EMP"
        profile_img = data.get('profile_img')
        status = "Active"
        contact = data.get('contact')
        p1 = generate_password_hash(password)

        cursor.execute("insert into users(id,name,email,password,role,profile_img,status,contact,org_id,created_at,created_by) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),%s)",(user_id,name,email,p1,roles,profile_img,status,contact,org_id,id))
        conn.commit()

        emp_det = str(uuid.uuid4())
        department_id = data.get('department_id')
        address = data.get('address')
        designation = data.get('designation')
        join_date = data.get('join_date')

        cursor.execute("insert into emp_detailes(id,user_id,org_id,department_id,address,designation,join_date) values(%s,%s,%s,%s,%s,%s,%s)",(emp_det,user_id,org_id,department_id,address,designation,join_date))
        conn.commit()

        sal_det = str(uuid.uuid4())
        base_salary = data.get('base_salary')
        agp = data.get('agp')
        da = data.get('da')
        dp = data.get('dp')
        hra = data.get('hra')
        tra = data.get('tra')
        cla = data.get('cla')
        bank_acc_no = data.get('bank_acc_no')
        ifsc_code = data.get('ifsc_code')
        bank_name = data.get('bank_name')
        bank_address = data.get('bank_address')
        #pt = data.get('pt')

        cursor.execute("insert into salary_detailes(id,user_id,org_id,base_salary,agp,da,dp,hra,tra,cla,bank_acc_no,ifsc_code,bank_name,bank_address,created_by,created_at) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())",(sal_det,user_id,org_id,base_salary,agp,da,dp,hra,tra,cla,bank_acc_no,ifsc_code,bank_name,bank_address,id))
        conn.commit()

        return jsonify({
            'status':'success',
            'message':'New Employee Added Successfully.'
        })

    except Exception as e:
        return jsonify({
            'status':'error',
            'message':str(e)
        })
    
