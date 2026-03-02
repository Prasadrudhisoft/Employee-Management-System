from flask import Flask, render_template

app = Flask(__name__)

from auth.auth import auth_bp
from Admin.Admin import admin_bp
from Manager.manager import manager_bp
from account.account import account_bp

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(manager_bp)
app.register_blueprint(account_bp)



@app.route('/')
def login_admin():
    return render_template('login.html')

@app.route('/admindashboard')
def admin_dashboard():
    return render_template('admindashboard.html')

@app.route('/managerdashboard')
def manager_dashboard():
    return render_template('managerdashboard.html')

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

if __name__ == '__main__':
    app.run(debug=True, port=5000)