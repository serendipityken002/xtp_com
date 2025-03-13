from flask import Flask, request, jsonify
from flask_cors import CORS
import jwt
import datetime
import os
from functools import wraps

app = Flask(__name__)
CORS(app)

# 配置
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')
app.config['JWT_EXPIRATION_DELTA'] = 24 * 60 * 60  # 过期时间24小时

# 模拟数据库
users_db = {}

# JWT验证装饰器
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # 从请求头获取token
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'message': '无效的令牌格式'}), 401
                
        if not token:
            return jsonify({'message': '缺少令牌'}), 401
            
        try:
            # 解码token
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = users_db.get(data['username'])
            if not current_user:
                return jsonify({'message': '用户不存在'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'message': '令牌已过期'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': '无效的令牌'}), 401
            
        # 将当前用户信息传递给被装饰的函数
        return f(current_user, *args, **kwargs)
    
    return decorated

# 注册接口
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': '请提供用户名和密码'}), 400
        
    username = data.get('username')
    
    if username in users_db:
        return jsonify({'message': '用户已存在'}), 409
    
    # 在实际应用中应对密码进行哈希处理
    users_db[username] = {
        'username': username,
        'password': data.get('password'),
        'name': data.get('name', ''),
        'role': data.get('role', 'user')
    }
    
    return jsonify({'message': '用户注册成功'}), 201

# 登录接口
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': '请提供用户名和密码'}), 400
    
    username = data.get('username')
    password = data.get('password')
    
    user = users_db.get(username)
    
    if not user or user['password'] != password:
        return jsonify({'message': '用户名或密码错误'}), 401
    
    # 生成JWT令牌
    token = jwt.encode({
        'username': username,
        'role': user.get('role', 'user'),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=app.config['JWT_EXPIRATION_DELTA'])
    }, app.config['SECRET_KEY'], algorithm="HS256")
    
    return jsonify({
        'message': '登录成功',
        'token': token,
        'username': username,
        'name': user.get('name', ''),
        'role': user.get('role', 'user')
    })

# 受保护的接口示例
@app.route('/api/protected', methods=['GET'])
@token_required
def protected(current_user):
    return jsonify({
        'message': '这是受保护的数据',
        'user': current_user['username'],
        'role': current_user['role']
    })

# 获取用户信息
@app.route('/api/user/info', methods=['GET'])
@token_required
def get_user_info(current_user):
    return jsonify({
        'username': current_user['username'],
        'name': current_user.get('name', ''),
        'role': current_user.get('role', 'user')
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)