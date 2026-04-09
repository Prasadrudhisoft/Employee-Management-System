from flask import Blueprint, request, jsonify
from connector import get_connection
import uuid
from decorators import jwt_required
import pymysql
from werkzeug.security import generate_password_hash
import os
import time
from models.models import otp_store, pending_data, generate_otp, send_otp_email

admin_bp = Blueprint('admin', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, '..', 'static', 'profile_imgs')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 2 * 1024 * 1024
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_profile_image(file):
    if not file or file.filename == '':
        return None, 'No file provided'
    if not allowed_file(file.filename):
        return None, 'Invalid file type. Only png, jpg, jpeg, webp are allowed'
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_FILE_SIZE:
        return None, f'File too large. Maximum allowed size is 2MB'
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    return filepath.replace('\\', '/'), None

# ------------------ STEP 1: Initiate Manager Addition (send OTP) ------------------
@admin_bp.route('/add_manager', methods=['POST'])
@jwt_required
def add_manager(id=None, org_id=None, role=None, org_name=None):
    cursor = None
    conn = None
    if role != 'Admin':
        return jsonify({'status': 'fail', 'message': 'Unauthorized Access'}), 403

    data = request.form
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

    pending = {
        'name': data.get('name'),
        'email': email,
        'password': data.get('password'),
        'contact': data.get('contact'),
        'department_id': data.get('department_id'),
        'address': data.get('address'),
        'designation': data.get('designation'),
        'join_date': data.get('join_date'),
        'base_salary': data.get('base_salary'),
        'agp': data.get('agp'),
        'da': data.get('da'),
        'dp': data.get('dp'),
        'hra': data.get('hra'),
        'tra': data.get('tra'),
        'cla': data.get('cla'),
        'bank_acc_no': data.get('bank_acc_no'),
        'ifsc_code': data.get('ifsc_code'),
        'bank_name': data.get('bank_name'),
        'bank_address': data.get('bank_address'),
        'profile_img': request.files.get('profile_img'),
        'submitted_by': id,
        'org_id': org_id,
        'org_name': org_name,
        'role': 'Manager'
    }

    otp = generate_otp()
    otp_store[email] = {'otp': otp, 'expires_at': time.time() + 300}
    pending_data[email] = pending

    success, error = send_otp_email(email, otp)
    if not success:
        otp_store.pop(email, None)
        pending_data.pop(email, None)
        return jsonify({'status': 'error', 'message': f'Failed to send OTP: {error}'}), 500

    return jsonify({
        'status': 'success',
        'message': 'OTP sent to the manager’s email. Please verify to complete creation.',
        'pending_id': email
    })

# ------------------ STEP 2: Verify OTP and Create Manager ------------------
@admin_bp.route('/verify_add_manager', methods=['POST'])
@jwt_required
def verify_add_manager(id=None, org_id=None, role=None, org_name=None):
    if role != 'Admin':
        return jsonify({'status': 'fail', 'message': 'Unauthorized Access'}), 403

    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')

    if not email or not otp:
        return jsonify({'status': 'fail', 'message': 'Email and OTP are required'}), 400

    stored = otp_store.get(email)
    print(otp_store)  # Debugging line to check OTP store contents
    if not stored or time.time() > stored['expires_at']:
        return jsonify({'status': 'fail', 'message': 'OTP expired or not requested'}), 400
    if stored['otp'] != otp:
        print(otp)
        return jsonify({'status': 'fail', 'message': 'Invalid OTP'}), 400

    pending = pending_data.pop(email, None)
    otp_store.pop(email, None)
    if not pending:
        return jsonify({'status': 'fail', 'message': 'No pending registration for this email'}), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        conn.begin()

        profile_img_path = None
        profile_file = pending.get('profile_img')
        if profile_file and profile_file.filename:
            profile_img_path, img_error = save_profile_image(profile_file)
            if img_error:
                raise Exception(img_error)

        user_id = str(uuid.uuid4())
        hashed_pw = generate_password_hash(pending['password'])

        cursor.execute("""
            INSERT INTO users(id, name, email, password, role, profile_img, status, contact, org_id, created_at, created_by, org_name)
            VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s)
        """, (user_id, pending['name'], email, hashed_pw, 'Manager', profile_img_path, 'Active',
              pending['contact'], pending['org_id'], pending['submitted_by'], pending['org_name']))

        emp_det_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO emp_detailes(id, user_id, org_id, department_id, address, designation, join_date)
            VALUES(%s, %s, %s, %s, %s, %s, %s)
        """, (emp_det_id, user_id, pending['org_id'], pending['department_id'], pending['address'],
              pending['designation'], pending['join_date']))

        sal_det_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO salary_detailes(id, user_id, org_id, base_salary, agp, da, dp, hra, tra, cla,
                bank_acc_no, ifsc_code, bank_name, bank_address, created_by, created_at)
            VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (sal_det_id, user_id, pending['org_id'], pending['base_salary'], pending['agp'],
              pending['da'], pending['dp'], pending['hra'], pending['tra'], pending['cla'],
              pending['bank_acc_no'], pending['ifsc_code'], pending['bank_name'], pending['bank_address'],
              pending['submitted_by']))

        conn.commit()
        return jsonify({'status': 'success', 'message': 'Manager added successfully after OTP verification'})

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ------------------ Existing Endpoints (unchanged) ------------------
@admin_bp.route('/adddepartments', methods=['POST'])
@jwt_required
def adddepartments(id=None, org_id=None, role=None, org_name=None):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        if role != 'Admin':
            return jsonify({'status': 'fail', 'message': 'Unauthorized Access'})
        data = request.json
        department = data.get("department")
        new_id = str(uuid.uuid4())
        cursor.execute("insert into departments(id,org_id,department_name, created_by, created_at) values(%s,%s,%s,%s,NOW())", (new_id, org_id, department, id))
        conn.commit()
        return jsonify({'status': 'success', 'message': 'Department Added Successfully'})
    except Exception as e:
        print(e)
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@admin_bp.route('/get_departments', methods=['GET'])
@jwt_required
def get_departments(id=None, org_id=None, role=None, org_name=None):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("SELECT * from departments where org_id = %s", (org_id,))
        dep = cursor.fetchall()
        return jsonify({'status': 'success', 'message': 'Departments Fetched Successfully', 'dep_data': dep})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@admin_bp.route('/total_managers', methods=['GET'])
@jwt_required
def total_managers(id=None, org_id=None, role=None, org_name=None):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        if role != 'Admin':
            return jsonify({'status': 'fail', 'message': 'Unauthorized Access'})
        cursor.execute("SELECT COUNT(*) FROM users WHERE role='Manager' AND org_id=%s", (org_id,))
        result = cursor.fetchone()
        managers = result['COUNT(*)'] if result else 0
        cursor.execute("SELECT COUNT(*) FROM departments WHERE org_id=%s", (org_id,))
        result = cursor.fetchone()
        dept = result['COUNT(*)'] if result else 0
        cursor.execute("SELECT COUNT(*) FROM users WHERE role!='Admin' AND org_id=%s", (org_id,))
        result = cursor.fetchone()
        total_emp = result['COUNT(*)'] if result else 0
        return jsonify({'status': 'success', 'message': 'Dashboard counts fetched successfully', 'managers': managers, 'dept': dept, 'total_emp': total_emp})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()