from flask import Flask, render_template, jsonify
from flask import send_from_directory
import os

app = Flask(__name__)


# ── ADD THESE TWO THINGS ──
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # ← line 1: add this

@app.errorhandler(413)                               # ← line 2: add this whole block
def file_too_large(e):
    return jsonify({'status': 'error', 'message': 'File too large. Max 2MB allowed.'}), 413
# ── END OF ADDITION ──

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'profile_imgs')



from auth.auth import auth_bp
from Admin.Admin import admin_bp
from Manager.manager import manager_bp
from account.account import account_bp
from leave import leave_bp
from models.models import models_bp

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(manager_bp)
app.register_blueprint(account_bp)
app.register_blueprint(leave_bp)
app.register_blueprint(models_bp)



@app.route('/')
def login_admin():
    return render_template('login.html')

@app.route('/admindashboard')
def admin_dashboard():
    return render_template('admindashboard.html')

@app.route('/managerdashboard')
def manager_dashboard():
    return render_template('managerdashboard.html')

@app.route('/empdashboard')
def empdashboard():
    return render_template('employeedashboard.html')

@app.route('/addmanager')
def add_manager():
    return render_template('addmanager.html')

@app.route('/addemp')
def add_emp():
    return render_template('addemployee.html')

@app.route('/adddepartments')
def add_department():
    return render_template('adddepartments.html')

@app.route('/salary_record')
def salary_record():
    return render_template('salary_record.html')

@app.route('/leave_requests')
def leave_requests():
    return render_template('leave_requests.html')

@app.route('/leave_types')
def leave_types():
    return render_template('leave_types.html')

@app.route('/holidays')
def holidays():
    return render_template('holidays.html')

@app.route('/employee/leaves')
def employee_leaves():
    return render_template('employee_leaves.html')

@app.route('/emp_status')
def emp_status():
    return render_template('employee_status.html')

@app.route('/static/profile_imgs/<filename>')
def serve_profile_img(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route('/apply_leave')
def apply_leave():
    return render_template('applyleave.html')

@app.route('/myleaves')
def my_leave():
    return render_template('myleaves.html')

@app.route('/leave_balance')
def leave_balance():
    return render_template('leavebalance.html')

@app.route('/holiday_calender')
def holiday_calender():
    return render_template('holidaycalender.html')


@app.route('/Leave_history')
def leave_history():
    return render_template('leavehistory.html')

@app.route('/forgot_password')
def forgot_password():
    return render_template('forgot_password.html')

@app.route('/staffManage')
def staffManage():
    return render_template('staffmanagement.html')

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5001)