from flask import Flask

app = Flask(__name__)

from auth.auth import auth_bp
from Admin.Admin import admin_bp
from Manager.manager import manager_bp

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(manager_bp)

if __name__ == ('__main__'):
    app.run(debug=True)