from flask import request, jsonify, Blueprint
from jose import jwt
from connector import get_connection
import pymysql
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from decorators import jwt_required
import os
from leave import _auto_create_balance_for_employee   # ← ADD THIS IMPORT AT TOP

manager_bp = Blueprint('manager',__name__)


BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, '..', 'static', 'profile_imgs')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB in bytes

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_profile_image(file):
    """Save uploaded file object to disk, return (web-safe path, error message)."""
    
    if not file or file.filename == '':
        return None, 'No file provided'
    
    if not allowed_file(file.filename):
        return None, 'Invalid file type. Only png, jpg, jpeg, webp are allowed'
    
    # ── Check file size ──
    file.seek(0, 2)              # Seek to end of file
    file_size = file.tell()      # Get size in bytes
    file.seek(0)                 # Reset back to start before saving

    if file_size > MAX_FILE_SIZE:
        return None, f'File too large. Maximum allowed size is 2MB'
    
    ext      = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    
    return filepath.replace('\\', '/'), None  # (path, no error)



def to_num(val):
    if val is None or str(val).strip() == '':
        return None
    return val

@manager_bp.route('/add_emp', methods=['GET', 'POST'])
@jwt_required
def add_emp(id=None, org_id=None, role=None, org_name=None):
    conn, cursor = None, None  # ← fix your finally bug too
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        if role != 'Manager':
            return jsonify({'status': 'fail', 'message': 'Unauthorized Access'})

        data = request.form

        user_id  = str(uuid.uuid4())
        name     = data.get('name')
        email    = data.get('email')
        password = data.get('password')
        roles    = "EMP"
        status   = "Active"
        contact  = data.get('contact')

        profile_file     = request.files.get('profile_img')
        profile_img_path, img_error = save_profile_image(profile_file)
        
        if img_error:
            return jsonify({'status': 'error', 'message': img_error}), 400
        p1               = generate_password_hash(password)

        # ── BEGIN TRANSACTION ──
        conn.begin()

        # ── Insert 1: users ──
        cursor.execute(
            """INSERT INTO users(id, name, email, password, role, profile_img, status, contact, org_id, created_at, created_by, org_name)
               VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s)""",
            (user_id, name, email, p1, roles, profile_img_path, status, contact, org_id, id, org_name)
        )

        # ── Insert 2: emp_detailes ──
        emp_det       = str(uuid.uuid4())
        department_id = data.get('department_id')
        address       = data.get('address')
        designation   = data.get('designation')
        join_date     = data.get('join_date')

        cursor.execute(
            """INSERT INTO emp_detailes(id, user_id, org_id, department_id, address, designation, join_date)
               VALUES(%s, %s, %s, %s, %s, %s, %s)""",
            (emp_det, user_id, org_id, department_id, address, designation, join_date)
        )

        # ── Insert 3: salary_detailes ──
        sal_det      = str(uuid.uuid4())
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
            (sal_det, user_id, org_id, base_salary, agp, da, dp, hra, tra, cla,
             bank_acc_no, ifsc_code, bank_name, bank_address, id)
        )

        # ── All 3 inserts succeeded — commit everything at once ──
        conn.commit()

        # ── Auto-create leave balance (runs after commit, non-critical) ──
        _auto_create_balance_for_employee(user_id, org_id, cursor, conn)

        return jsonify({'status': 'success', 'message': 'New Employee Added Successfully.'})

    except Exception as e:
        if conn:
            conn.rollback()  # ← Undoes ALL inserts if any one failed
        return jsonify({'status': 'error', 'message': str(e)})

    finally:
        if cursor: cursor.close()
        if conn: conn.close()
    
@manager_bp.route('/get_emp', methods=['GET'])
@jwt_required
def get_emp(role = None, id = None, org_id = None, org_name = None):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        if role != 'Manager':
            return{
                'status':'fail',
                'message':'unauthozized Access'
            }

        cursor.execute("SELECT * FROM USERS WHERE org_id = %s and Status = 'Active' and role = 'EMP'",(org_id,))
        active_users = cursor.fetchall()

        cursor.execute("SELECT * FROM USERS WHERE org_id = %s and Status != 'Active' and role = 'EMP'",(org_id,))
        deactive_users = cursor.fetchall()

        if not active_users and not deactive_users:
            return jsonify({
                'status':'fail',
                'message':'No User Found'
            })
        
        else:
            return jsonify({
                'status':'success',
                'message':'Employees Fetched Succcessfully..',
                'active_users':active_users,
                'deactive_users':deactive_users
            })
        

    except Exception as e:
        return jsonify({
            'status':'Error',
            'message':str(e)
        })
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
# ── Add this route to your manager_bp in manager.py ──

@manager_bp.route('/toggle_emp_status', methods=['POST'])
@jwt_required
def toggle_emp_status(id=None, org_id=None, role=None, org_name=None):
    conn = None
    cursor = None
    """
    Toggle employee status between 'Active' and 'Deactive'.
    Expects JSON body: { "user_id": "<employee_uuid>" }
    Only operates on employees belonging to the manager's org.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        if role != 'Manager':
            return{
                'status':'fail',
                'message':'unauthozized Access'
            }

        data = request.get_json()
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({'status': 'error', 'message': 'user_id is required'}), 400

        # Fetch current status — scoped to manager's org for security
        cursor.execute(
            "SELECT id, name, status FROM users WHERE id = %s AND org_id = %s AND role = 'EMP'",
            (user_id, org_id)
        )
        emp = cursor.fetchone()

        if not emp:
            return jsonify({'status': 'error', 'message': 'Employee not found'}), 404

        # Flip status
        new_status = 'Deactive' if emp['status'] == 'Active' else 'Active'

        cursor.execute(
            "UPDATE users SET status = %s WHERE id = %s AND org_id = %s",
            (new_status, user_id, org_id)
        )
        conn.commit()

        return jsonify({
            'status': 'success',
            'message': f"Employee status updated to '{new_status}'.",
            'user_id': user_id,
            'new_status': new_status
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@manager_bp.route('/total_emp',methods=['GET'])
@jwt_required
def total_emp(role=None, id=None, org_id = None, org_name = None):
    conn = None
    cursor = None
    try:

        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        if role != 'Manager':
            return{
                'status':'fail',
                'message':'unauthozized Access'
            }

        cursor.execute("select count(*) as total_emp, SUM(status='Active') as active_emp, SUM(status='Deactive')as deactive_emp from users where org_id = %s AND role!='Admin'",(org_id,))
        total_emp = cursor.fetchone()

        return jsonify({
            'status':'success',
            'message':'Successfully Total Counts Fetched..',
            'total_emp':total_emp,
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