from flask import Flask, render_template

app = Flask(__name__)

from auth.auth import auth_bp
from Admin.Admin import admin_bp
from Manager.manager import manager_bp
from account.account import account_bp
from leave import leave_bp

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(manager_bp)
app.register_blueprint(account_bp)
app.register_blueprint(leave_bp)



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


if __name__ == '__main__':
    app.run(debug=True, port=5000)