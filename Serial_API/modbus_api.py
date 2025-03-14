"""
Modbus API模块
提供Modbus协议的HTTP API接口
"""
import os
import time
import yaml
from flask import Flask, request, jsonify, Blueprint
from datetime import datetime

from .modbus_handler import ModbusFrame, ModbusResponseValidator, ModbusDatabase

# 加载配置文件
config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
with open(config_path, 'r', encoding='utf-8') as file:
    config = yaml.safe_load(file)

# 获取配置
max_entries = config.get('max_entries', 100)
db_path = os.path.join(os.path.dirname(__file__), 'data', 'modbus_frames.db')

# 创建数据库目录
os.makedirs(os.path.dirname(db_path), exist_ok=True)

# 初始化数据库
db = ModbusDatabase(db_path)

# 创建响应验证器
validator = ModbusResponseValidator()

# 创建蓝图
modbus_bp = Blueprint('modbus', __name__)

# 保存串口对象的字典 (从serialAPI中导入)
serial_ports = {}

@modbus_bp.route('/send', methods=['POST'])
def send_modbus_frame():
    """发送Modbus帧"""
    try:
        port = request.json['port']
        frame_hex = request.json['frame']
        
        # 检查串口是否存在和打开
        if port not in serial_ports or not serial_ports[port].is_open:
            return jsonify({
                'status': 'error',
                'message': f'串口 {port} 未打开'
            })
        
        # 创建Modbus帧对象
        frame = ModbusFrame(hex_string=frame_hex)
        
        if not frame.is_valid():
            return jsonify({
                'status': 'error',
                'message': 'Modbus帧无效，CRC校验失败'
            })
        
        # 保存请求帧到数据库
        request_id = db.save_frame(frame, frame_type='request')
        
        # 清除之前的缓冲区
        validator.clear()
        
        # 发送数据
        ser = serial_ports[port]
        ser.write(bytes(frame.bytes))
        
        # 等待响应
        start_time = time.time()
        response_frame = None
        
        while time.time() - start_time < validator.timeout:
            # 读取可用数据
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                validator.add_data(data)
            
            # 尝试提取响应
            response_frame = validator.extract_response(frame)
            if response_frame:
                break
            
            time.sleep(0.01)
        
        result = {
            'status': 'success',
            'message': 'Modbus帧已发送',
            'requestId': request_id,
            'request': frame_hex
        }
        
        # 处理响应
        if response_frame:
            # 验证响应帧
            is_valid = response_frame.is_valid()
            error = None if is_valid else 'CRC校验失败'
            
            # 保存响应帧到数据库
            response_id = db.save_frame(
                response_frame, 
                frame_type='response',
                request_id=request_id,
                error=error
            )
            
            result['response'] = response_frame.to_hex_string()
            result['responseId'] = response_id
            result['valid'] = is_valid
        else:
            result['response'] = None
            result['message'] += '，但未收到响应'
        
        # 清理旧的帧记录
        db.clean_old_frames(max_entries)
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Modbus发送错误: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@modbus_bp.route('/history', methods=['GET'])
def get_frame_history():
    """获取帧历史记录"""
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        frames = db.get_frames(limit, offset)
        
        return jsonify({
            'status': 'success',
            'frames': frames
        })
        
    except Exception as e:
        print(f"获取历史记录错误: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@modbus_bp.route('/frame/<int:frame_id>', methods=['GET'])
def get_frame(frame_id):
    """获取特定帧"""
    try:
        frame = db.get_frame_by_id(frame_id)
        
        if frame:
            return jsonify({
                'status': 'success',
                'frame': frame
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'找不到ID为 {frame_id} 的帧'
            })
            
    except Exception as e:
        print(f"获取帧错误: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@modbus_bp.route('/response/<int:request_id>', methods=['GET'])
def get_response(request_id):
    """获取请求对应的响应"""
    try:
        response = db.get_response_for_request(request_id)
        
        if response:
            return jsonify({
                'status': 'success',
                'response': response
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'找不到请求ID为 {request_id} 的响应'
            })
            
    except Exception as e:
        print(f"获取响应错误: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@modbus_bp.route('/frames/range', methods=['GET'])
def get_frames_by_range():
    """按时间范围获取帧"""
    try:
        start_time = request.args.get('startTime', None)
        end_time = request.args.get('endTime', None)
        
        if not start_time or not end_time:
            return jsonify({
                'status': 'error',
                'message': '必须提供开始和结束时间'
            })
        
        frames = db.get_frames_by_time_range(start_time, end_time)
        
        return jsonify({
            'status': 'success',
            'frames': frames
        })
        
    except Exception as e:
        print(f"按范围获取帧错误: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }) 