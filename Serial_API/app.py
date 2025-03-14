from flask import Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# 导入蓝图
from modbus import modbus_bp
from test import test_bp

# 注册蓝图
app.register_blueprint(modbus_bp, url_prefix='/api/modbus')
app.register_blueprint(test_bp, url_prefix='/api/serial')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
