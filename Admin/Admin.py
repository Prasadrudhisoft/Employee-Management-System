from flask import Flask, Blueprint, request, Response, jsonify
from connector import get_connection
import uuid
from decorators import jwt_required
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash

admin_bp = Blueprint('admin',__name__)

@admin_bp.route('/adddepartments', methods = ['GET','POST'])
@jwt_required
def adddepartments(id = None, org_id = None, role = None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        data = request.json
        department = data.get("department")
        
        new_id = str(uuid.uuid4())

        cursor.execute("insert into departments(id,org_id,department_name, created_by, created_at) values(%s,%s,%s,%s,NOW())",(new_id, org_id, department, id))
        conn.commit()
        return jsonify({
            'status':'success',
            'message':'Department Added Successfully'
        })
    except Exception as e:
        print(e)
        return jsonify({
            'status':'error',
            'message':str(e)
        })
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/get_departments', methods=['GET'])
@jwt_required
def get_departments(id = None, org_id = None, role = None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        cursor.execute("SELECT * from departments where org_id = %s", (org_id,))
        dep = cursor.fetchall()

        return jsonify({
            'status':'success',
            'message':'Departments Fetched Successfully',
            'dep_data':dep
        })
    except Exception as e:
        return jsonify({
            'status':'error',
            'message':str(e)
        })
    
@admin_bp.route('/add_manager', methods=['GET','POST'])
@jwt_required
def add_manager(id = None, org_id = None, role= None):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        data = request.json
        user_id = str(uuid.uuid4())
        name = data.get("name")
        email =  data.get("email")
        password = data.get("password")
        roles = "Manager"
        profile_img = data.get("profile_img")
        status = "Active"
        contact = data.get("contact")

        p1 = generate_password_hash(password)

        cursor.execute("insert into users(id,Name,Email,Password,role,Profile_img,Status,Contact,org_id,created_at,Created_by) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),%s)",(user_id,name,email,p1,roles,profile_img,status,contact,org_id,id))
        conn.commit()

        emp_id = str(uuid.uuid4())
        department_id = data.get("department_id")
        address = data.get("address")
        designation = data.get("designation")
        join_date = data.get("join_date")

        cursor.execute("insert into emp_detailes(id, user_id, org_id, department_id, address, designation, join_date) values(%s,%s,%s,%s,%s,%s,%s)",(emp_id,user_id,org_id,department_id,address,designation,join_date))
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


        cursor.execute("insert into salary_detailes(id, user_id, org_id, base_salary, agp, da, dp, hra, tra, cla, bank_acc_no, ifsc_code, bank_name, bank_address, created_by, created_at) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())",(sal_det,user_id, org_id, base_salary,agp,da,dp,hra,tra,cla,bank_acc_no,ifsc_code,bank_name,bank_address,id))
        conn.commit()

        return jsonify({
            'status':'success',
            'message':'user Added In Successfully.'
        })
    except Exception as e:
        print(e)
        return jsonify({
            'status':'error',
            'message':str(e)
        })
