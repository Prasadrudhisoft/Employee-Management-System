from flask import request, jsonify, Blueprint
from connector import get_connection
import pymysql
import uuid
from werkzeug.security import generate_password_hash
from decorators import jwt_required
import os
from leave import _auto_create_balance_for_employee
import time
from models.models import otp_store, pending_data, generate_otp, send_otp_email

manager_bp = Blueprint('manager', __name__)

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

# ------------------ STEP 1: Initiate Employee Addition (send OTP) ------------------
@manager_bp.route('/add_emp', methods=['POST'])
@jwt_required
def add_emp(id=None, org_id=None, role=None, org_name=None):
    conn = None
    cursor = None
    if role != 'Manager':
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
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return jsonify({'status': 'fail', 'message': 'Email already registered'}), 409
    if cursor:
        cursor.close()
    if conn:
        conn.close()

    # Read file bytes immediately while the request stream is still open
    profile_file = request.files.get('profile_img')
    profile_img_bytes = None
    profile_img_filename = None
    if profile_file and profile_file.filename:
        profile_img_bytes = profile_file.read()
        profile_img_filename = profile_file.filename

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
        'profile_img_bytes': profile_img_bytes,
        'profile_img_filename': profile_img_filename,
        'submitted_by': id,
        'org_id': org_id,
        'org_name': org_name,
        'role': 'EMP'
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
        'message': 'OTP sent to the employee\'s email. Please verify to complete creation.',
        'pending_id': email
    })

# ------------------ STEP 2: Verify OTP and Create Employee ------------------
@manager_bp.route('/verify_add_emp', methods=['POST'])
@jwt_required
def verify_add_emp(id=None, org_id=None, role=None, org_name=None):
    conn = None
    cursor = None

    if role != 'Manager':
        return jsonify({'status': 'fail', 'message': 'Unauthorized Access'}), 403

    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')

    if not email or not otp:
        return jsonify({'status': 'fail', 'message': 'Email and OTP are required'}), 400

    stored = otp_store.get(email)
    if not stored or time.time() > stored['expires_at']:
        return jsonify({'status': 'fail', 'message': 'OTP expired or not requested'}), 400
    if stored['otp'] != otp:
        return jsonify({'status': 'fail', 'message': 'Invalid OTP'}), 400

    pending = pending_data.pop(email, None)
    otp_store.pop(email, None)
    if not pending:
        return jsonify({'status': 'fail', 'message': 'No pending registration for this email'}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        conn.begin()

        # Save profile image from stored bytes
        profile_img_path = None
        img_bytes = pending.get('profile_img_bytes')
        img_filename = pending.get('profile_img_filename')
        if img_bytes and img_filename:
            if not allowed_file(img_filename):
                raise Exception('Invalid file type. Only png, jpg, jpeg, webp are allowed')
            if len(img_bytes) > MAX_FILE_SIZE:
                raise Exception('File too large. Maximum allowed size is 2MB')
            ext = img_filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4()}.{ext}"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            with open(filepath, 'wb') as f:
                f.write(img_bytes)
            profile_img_path = f"static/profile_imgs/{filename}"

        user_id = str(uuid.uuid4())
        hashed_pw = generate_password_hash(pending['password'])

        cursor.execute("""
            INSERT INTO users(id, name, email, password, role, profile_img, status, contact, org_id, created_at, created_by, org_name)
            VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s)
        """, (user_id, pending['name'], email, hashed_pw, 'EMP', profile_img_path, 'Active',
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
        _auto_create_balance_for_employee(user_id, pending['org_id'], cursor, conn)

        return jsonify({'status': 'success', 'message': 'Employee added successfully after OTP verification'})

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
@manager_bp.route('/get_emp', methods=['GET'])
@jwt_required
def get_emp(role=None, id=None, org_id=None, org_name=None):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        if role != 'Manager':
            return jsonify({'status': 'fail', 'message': 'Unauthorized Access'})
        cursor.execute("SELECT * FROM users WHERE org_id = %s and Status = 'Active' and role = 'EMP'", (org_id,))
        active_users = cursor.fetchall()
        cursor.execute("SELECT * FROM users WHERE org_id = %s and Status != 'Active' and role = 'EMP'", (org_id,))
        deactive_users = cursor.fetchall()
        if not active_users and not deactive_users:
            return jsonify({'status': 'fail', 'message': 'No User Found'})
        return jsonify({'status': 'success', 'message': 'Employees Fetched Successfully', 'active_users': active_users, 'deactive_users': deactive_users})
    except Exception as e:
        return jsonify({'status': 'Error', 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@manager_bp.route('/toggle_emp_status', methods=['POST'])
@jwt_required
def toggle_emp_status(id=None, org_id=None, role=None, org_name=None):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        if role != 'Manager':
            return jsonify({'status': 'fail', 'message': 'Unauthorized Access'})
        data = request.get_json()
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({'status': 'error', 'message': 'user_id is required'}), 400
        cursor.execute("SELECT id, name, status FROM users WHERE id = %s AND org_id = %s AND role = 'EMP'", (user_id, org_id))
        emp = cursor.fetchone()
        if not emp:
            return jsonify({'status': 'error', 'message': 'Employee not found'}), 404
        new_status = 'Deactive' if emp['status'] == 'Active' else 'Active'
        cursor.execute("UPDATE users SET status = %s WHERE id = %s AND org_id = %s", (new_status, user_id, org_id))
        conn.commit()
        return jsonify({'status': 'success', 'message': f"Employee status updated to '{new_status}'.", 'user_id': user_id, 'new_status': new_status})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@manager_bp.route('/total_emp', methods=['GET'])
@jwt_required
def total_emp(role=None, id=None, org_id=None, org_name=None):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        if role != 'Manager':
            return jsonify({'status': 'fail', 'message': 'Unauthorized Access'})
        cursor.execute("select count(*) as total_emp, SUM(status='Active') as active_emp, SUM(status='Deactive')as deactive_emp from users where org_id = %s AND role!='Admin'", (org_id,))
        total_emp = cursor.fetchone()
        return jsonify({'status': 'success', 'message': 'Successfully Total Counts Fetched', 'total_emp': total_emp})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()