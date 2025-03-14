import serial
import serial.tools.list_ports

from flask import Blueprint, request, jsonify

import os
import yaml
import threading
import time

test_bp = Blueprint('test', __name__)

# 加载配置文件
config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
with open(config_path, 'r', encoding='utf-8') as file:
    config = yaml.safe_load(file)

# 使用配置
host = config['server']['host']
port = config['server']['port']
debug = config['server']['debug']

baudrate_default = config['default_serial_config']['baudrate']
timeout_default = config['default_serial_config']['timeout']
max_length = config['max_entries']

serial_ports = {}
serial_data = {}
is_reading = {}
read_threads = {}

def init_serial(port_name, baudrate=baudrate_default, timeout=timeout_default):
    # 检查端口是否存在
    available_ports = [p.device for p in serial.tools.list_ports.comports()]
    if port_name not in available_ports:
        print(f"错误：找不到串口 {port_name}")
        print(f"可用串口: {available_ports}")
        return False

    # 如果串口已经打开，先关闭
    if port_name in serial_ports and serial_ports[port_name].is_open:
        serial_ports[port_name].close()

    # 创建新的串口连接
    ser = serial.Serial(
        port=port_name,
        baudrate=baudrate,
        timeout=timeout
    )
    
    if not ser.is_open:
        ser.open()

    # 初始化该串口的数据存储
    serial_ports[port_name] = ser
    serial_data[port_name] = []
    is_reading[port_name] = True

    print(f"成功连接到串口 {port_name}, 波特率: {baudrate}")
    return True

def read_serial(port):
    """读取指定串口的数据"""
    while is_reading.get(port, False):
        # 循环到 is_reading[port] 为 False 时退出
        if port in serial_ports:
            try:
                ser = serial_ports[port]
                if ser.in_waiting > 0:
                    # 检查串行端口的接收缓冲区是否有可读的数据 
                    data = ser.readline().decode('utf-8').strip()
                    serial_data[port].append(f'\n接收：{data}')
                    if len(serial_data[port]) > max_length:
                        # 保留最新的数据
                        serial_data[port].pop(0)
            except Exception as e:
                print(f"读取错误 ({port}): {e}")
        time.sleep(0.1)

@test_bp.route('/')
def index():
    """
    返回当前可用串口列表
    """
    available_ports = [p.device for p in serial.tools.list_ports.comports()]
    return {'ports': available_ports}

@test_bp.route('/ports', methods=['GET'])
def get_available_ports():
    """获取可用的串口列表"""
    available_ports = [p.device for p in serial.tools.list_ports.comports()]
    return jsonify({'ports': available_ports})

@test_bp.route('/start', methods=['POST'])
def start_serial():
    """启动指定串口"""
    try:
        port = request.json['port']
        baudrate = int(request.json.get('baudrate', baudrate_default))

        if init_serial(port, baudrate):
            # 启动串口线程
            thread = threading.Thread(target=read_serial, args=(port,))
            thread.start()
            read_threads[port] = thread

            return jsonify({
                'status': 'success',
                'message': f"串口 {port} 启动成功"
            })
        return jsonify({
            'status': 'error',
            'message': '串口初始化失败'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@test_bp.route('/stop', methods=['POST'])
def stop_serial():
    """停止指定串口"""
    try:
        port = request.json['port']
        if port in serial_ports:
            is_reading[port] = False
            serial_ports[port].close()
            del serial_ports[port]
            return jsonify({"status": "success"})
        return jsonify({
            'status': 'error',
            'message': '串口不存在'
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@test_bp.route('/send', methods=['POST'])
def send_data():
    """向指定串口发送数据"""
    port = request.json['port']
    data = request.json['data']
    print(f"发送数据 ({port}): {data}")
    if port in serial_ports:
        try:
            serial_ports[port].write(data.encode('utf-8'))
            serial_data[port].append(f"\n发送： {data}")
            return jsonify({
                "status": "success",
                "message": f"发送数据成功: {data}"
            })
        except Exception as e:
            return jsonify({
                "status": "send_error",
                "message": str(e)
            })

@test_bp.route('/status', methods=['POST'])
def get_status():
    """获取指定串口的状态"""
    port = request.json['port']

    if port in serial_ports:
        is_open = port in serial_ports and serial_ports[port].is_open

        return jsonify({
            "isOpen": is_open,
            "port": port if is_open else None,
            "baudrate": serial_ports[port].baudrate if is_open else None,
            "data": serial_data.get(port, [])
        })

    return jsonify({
        "isOpen": False,
        "port": None,
        "baudrate": None,
        "data": []
    })