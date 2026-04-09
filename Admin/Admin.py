from flask import Flask, Blueprint, request, Response, jsonify
from connector import get_connection
import uuid
from decorators import jwt_required
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash
import os

admin_bp = Blueprint('admin',__name__)


UPLOAD_FOLDER = 'static/profile_imgs'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_profile_image(file):
    """Save uploaded file object to disk, return web-safe path."""
    if not file or file.filename == '':
        return ''
    if not allowed_file(file.filename):
        return ''
    
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    
    return filepath.replace('\\', '/')  # web-safe path


@admin_bp.route('/adddepartments', methods = ['POST'])
@jwt_required
def adddepartments(id = None, org_id = None, role = None, org_name=None):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        if role != 'Admin':
            return{
                'status':'fail',
                'message':'unauthozized Access'
            }

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
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        

@admin_bp.route('/get_departments', methods=['GET'])
@jwt_required
def get_departments(id = None, org_id = None, role = None, org_name=None):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        if role != 'Admin':
            return{
                'status':'fail',
                'message':'unauthozized Access'
            }

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
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    
@admin_bp.route('/add_manager', methods=['POST'])
@jwt_required
def add_manager(id=None, org_id=None, role=None, org_name=None):
    conn, cursor = None, None  # ← fix your finally bug too
    try:
        conn = get_connection()
        cursor = conn.cursor()

        if role != 'Admin':
            return jsonify({'status': 'fail', 'message': 'Unauthorized Access'})

        data = request.form

        name         = data.get("name")
        email        = data.get("email")
        password     = data.get("password")
        contact      = data.get("contact")
        roles        = "Manager"
        status       = "Active"

        profile_file     = request.files.get("profile_img")
        profile_img_path = save_profile_image(profile_file)
        hashed_password  = generate_password_hash(password)

        # ── BEGIN TRANSACTION ──
        conn.begin()

        # ── Insert 1: users ──
        user_id = str(uuid.uuid4())
        cursor.execute(
            """INSERT INTO users(id, Name, Email, Password, role, Profile_img, Status, Contact, org_id, created_at, Created_by, org_name)
               VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s)""",
            (user_id, name, email, hashed_password, roles, profile_img_path, status, contact, org_id, id, org_name)
        )

        # ── Insert 2: emp_detailes ──
        emp_id        = str(uuid.uuid4())
        department_id = data.get("department_id")
        address       = data.get("address")
        designation   = data.get("designation")
        join_date     = data.get("join_date")

        cursor.execute(
            """INSERT INTO emp_detailes(id, user_id, org_id, department_id, address, designation, join_date)
               VALUES(%s, %s, %s, %s, %s, %s, %s)""",
            (emp_id, user_id, org_id, department_id, address, designation, join_date)
        )

        # ── Insert 3: salary_detailes ──
        sal_id       = str(uuid.uuid4())
        base_salary  = data.get('base_salary')
        agp          = data.get('agp')
        da           = data.get('da')
        dp           = data.get('dp')
        hra          = data.get('hra')
        tra          = data.get('tra')
        cla          = data.get('cla')
        bank_acc_no  = data.get('bank_acc_no')
        ifsc_code    = data.get('ifsc_code')
        bank_name    = data.get('bank_name')
        bank_address = data.get('bank_address')

        cursor.execute(
            """INSERT INTO salary_detailes(id, user_id, org_id, base_salary, agp, da, dp, hra, tra, cla,
               bank_acc_no, ifsc_code, bank_name, bank_address, created_by, created_at)
               VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
            (sal_id, user_id, org_id, base_salary, agp, da, dp, hra, tra, cla,
             bank_acc_no, ifsc_code, bank_name, bank_address, id)
        )

        # ── All 3 inserts succeeded — commit everything at once ──
        conn.commit()

        return jsonify({'status': 'success', 'message': 'Manager Added Successfully.'})

    except Exception as e:
        if conn:
            conn.rollback()  # ← Undoes ALL inserts if any one failed
        print(e)
        return jsonify({'status': 'error', 'message': str(e)})

    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@admin_bp.route('/total_managers', methods=['GET'])
@jwt_required
def total_managers(org_name=None, id=None, role=None, org_id=None):
    conn = None
    cursor = None
    try:

        conn = get_connection()
        cursor = conn.cursor()

        if role != 'Admin':
            return{
                'status':'fail',
                'message':'unauthozized Access'
            }

        cursor.execute("SELECT COUNT(*) FROM users WHERE role='Manager' AND org_id=%s", (org_id,))
        result = cursor.fetchone()
        managers = result['COUNT(*)'] if result else 0

        cursor.execute("SELECT COUNT(*) FROM departments WHERE org_id=%s", (org_id,))
        result = cursor.fetchone()
        dept = result['COUNT(*)'] if result else 0

        cursor.execute("SELECT COUNT(*) FROM users WHERE role!='Admin' AND org_id=%s", (org_id,))
        result = cursor.fetchone()
        total_emp = result['COUNT(*)'] if result else 0

        return jsonify({
            'status': 'success',
            'message': 'Dashboard counts fetched successfully',
            'managers': managers,
            'dept': dept,
            'total_emp': total_emp
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()