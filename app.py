from flask import Flask, render_template

app = Flask(__name__)

from auth.auth import auth_bp
from Admin.Admin import admin_bp
from Manager.manager import manager_bp

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(manager_bp)



@app.route('/', methods=['GET'])
def login_admin():
    return render_template('login.html')

@app.route('/admindashboard')
def admin_dashboard():
    return render_template('admindashboard.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)