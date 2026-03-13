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

# ── Same upload config as admin.py ──
UPLOAD_FOLDER = 'static/profile_imgs'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_profile_image(file):
    if not file or file.filename == '':
        return ''
    if not allowed_file(file.filename):
        return ''
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    return filepath.replace('\\', '/')

def to_num(val):
    if val is None or str(val).strip() == '':
        return None
    return val

@manager_bp.route('/add_emp', methods=['GET','POST'])
@jwt_required
def add_emp(id = None, org_id = None, role = None, org_name = None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        data = request.form
        user_id = str(uuid.uuid4())
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        roles = "EMP"
        status = "Active"
        contact = data.get('contact')

        # ── Save image file, get path ──
        profile_file    = request.files.get('profile_img')
        profile_img_path = save_profile_image(profile_file)

        p1 = generate_password_hash(password)

        cursor.execute("insert into users(id,name,email,password,role,profile_img,status,contact,org_id,created_at,created_by,org_name) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),%s,%s)",(user_id,name,email,p1,roles,profile_img_path,status,contact,org_id,id,org_name))
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

        # ↓↓↓ ADD THIS — auto-creates leave balance for all existing leave types
        _auto_create_balance_for_employee(user_id, org_id, cursor, conn)

        return jsonify({
            'status':'success',
            'message':'New Employee Added Successfully.'
        })

    except Exception as e:
        return jsonify({
            'status':'error',
            'message':str(e)
        })
    
    finally:
        cursor.close()
        conn.close()
    
@manager_bp.route('/get_emp', methods=['GET'])
@jwt_required
def get_emp(role = None, id = None, org_id = None, org_name = None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

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
    
# ── Add this route to your manager_bp in manager.py ──

@manager_bp.route('/toggle_emp_status', methods=['POST'])
@jwt_required
def toggle_emp_status(id=None, org_id=None, role=None, org_name=None):
    """
    Toggle employee status between 'Active' and 'Deactive'.
    Expects JSON body: { "user_id": "<employee_uuid>" }
    Only operates on employees belonging to the manager's org.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

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
        cursor.close()
        conn.close()


@manager_bp.route('/total_emp',methods=['GET'])
@jwt_required
def total_emp(role=None, id=None, org_id = None, org_name = None):
    try:

        conn = get_connection()
        cursor = conn.cursor()

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
        cursor.close()
        conn.close()