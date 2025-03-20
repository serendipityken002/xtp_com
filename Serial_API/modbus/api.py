from flask import Flask, request, jsonify
from flask_cors import CORS
from dataprocess import send_data, process_data_thread, process_data, return_data_num
from serial_serve import start_serial_process
import socket
import yaml
import time
import logging
from logging.config import dictConfig
from datetime import datetime
import os
import threading
import json

app = Flask(__name__)
CORS(app)

def setup_logging():
    log_dir = 'logs'
    error_log_dir = os.path.join(log_dir, 'wrong_log')
    print_log_dir = os.path.join(log_dir, 'print_log')

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    if not os.path.exists(error_log_dir):
        os.makedirs(error_log_dir)
    if not os.path.exists(print_log_dir):
        os.makedirs(print_log_dir)

    today_str = datetime.now().strftime('%Y-%m-%d')
    error_today_dir = os.path.join(error_log_dir, today_str)
    print_today_dir = os.path.join(print_log_dir, today_str)
    if not os.path.exists(error_today_dir):
        os.makedirs(error_today_dir)
    if not os.path.exists(print_today_dir):
        os.makedirs(print_today_dir)

    # time_now = datetime.now().strftime('%H-%M-%S')
    error_log_file = os.path.join(error_today_dir, f'error_{today_str}.txt')
    print_log_file = os.path.join(print_today_dir, f'debug_{today_str}.log')

    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'INFO',
                'formatter': 'standard',
                'stream': 'ext://sys.stdout',
            },
            'error_file': {
                'class': 'logging.FileHandler',
                'level': 'ERROR',
                'formatter': 'standard',
                'filename': error_log_file,
                'mode': 'a',
                'encoding': 'utf-8',  # 指定编码为UTF-8
            },
            'print_file': {
                'class': 'logging.FileHandler',
                'level': 'DEBUG',
                'formatter': 'standard',
                'filename': print_log_file,
                'mode': 'a',
                'encoding': 'utf-8',  # 指定编码为UTF-8
            },
        },
        'loggers': {
            '': {  # root logger
                'handlers': ['console', 'error_file', 'print_file'],
                'level': 'DEBUG',
                'propagate': True
            },
            'SerialServer': {
                'handlers': ['console', 'error_file', 'print_file'],
                'level': 'DEBUG',
                'propagate': False
            },
        }
    }

    dictConfig(LOGGING_CONFIG)

setup_logging()

# 加载配置文件
config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
with open(config_path, 'r', encoding='utf-8') as file:
    config = yaml.safe_load(file)

# 全局变量
_server_socket = None
_is_running = False
_logger = logging.getLogger(__name__)

host = config['tcp_server']['host']
port = config['tcp_server']['port']
max_connections = config['tcp_server']['max_connections']

buffer_size = config['tcp_server']['buffer_size']
max_bytes_per_request = config['tcp_server']['max_bytes_per_request']

def handle_client(client_socket, client_address):
    """处理客户端连接"""
    global _logger, _is_running
    _logger.info(f"客户端已连接: {client_address}")
    
    try:
        # 设置接收超时
        client_socket.settimeout(5.0)
        
        while _is_running:
            try:
                # 接收客户端请求
                data = client_socket.recv(buffer_size)
                if not data:
                    _logger.info(f"客户端断开连接: {client_address}")
                    break
                    
                # 限制接收数据的字节数
                if len(data) > max_bytes_per_request:
                    response = {"status": "error", "message": f"接收数据超过最大限制: {max_bytes_per_request} 字节"}
                    client_socket.send(json.dumps(response).encode('utf-8'))
                    continue
                
                # 解析JSON请求
                try:
                    request = json.loads(data.decode('utf-8'))
                    _logger.debug(f"收到请求: {request}")
                except json.JSONDecodeError:
                    response = {"status": "error", "message": "无效的JSON格式"}
                    client_socket.send(json.dumps(response).encode('utf-8')) 
                    _logger.error("无效的JSON格式")
                    continue
                
                # 处理请求
                if request.get('action') == 'send':
                    # 发送数据
                    data_to_send = request.get('data')

                    if not data_to_send:
                        response = {"status": "error", "message": "缺少data参数"}
                    else:
                        slave_adress = data_to_send[0]
                        function_code = data_to_send[1]
                        start_address = data_to_send[2]
                        quantity = data_to_send[3]
                        success = send_data(slave_adress, function_code, start_address, quantity)
                        if success:
                            response = {"status": "success", "message": f"成功发送数据: {data_to_send}"}
                        else:
                            response = {"status": "error", "message": f"发送数据失败: {data_to_send}"}
                            
                elif request.get('action') == 'receive':
                    # 接收数据
                    num = request.get('num')
                    if not num:
                        response = {"status": "error", "message": "缺少num参数"}
                    received_data = process_data(num)
                    if received_data:
                        response = {
                            "status": "success", 
                            "data": received_data,
                            "length": len(received_data)
                        }
                    else:
                        response = {"status": "success", "data": "", "length": 0}
                        
                elif request.get('action') == 'queue_size':
                    # 获取队列大小
                    size = return_data_num()
                    _logger.info(f"当前剩余数据帧个数：{size}")
                    response = {"status": "success", "size": size}
                    
                # elif request.get('action') == 'status':
                #     # 获取服务状态
                #     response = {"status": "success", "running": is_running}
                    
                # elif request.get('action') == 'queue_info':
                #     # 获取队列信息
                #     info = get_queue_info()
                #     response = {"status": "success", "queue_info": info}
                    
                # elif request.get('action') == 'reset_overflow':
                #     # 重置溢出标志
                #     previous = reset_queue_overflow()
                #     response = {"status": "success", "previous_overflow": previous}
                    
                else:
                    response = {"status": "error", "message": f"未知的action参数: {request.get('action')}"}
                    
                # 发送响应
                _logger.debug(f"发送响应: {response}")
                client_socket.send(json.dumps(response).encode('utf-8'))

            except socket.timeout:
                # 接收超时，继续循环
                continue
            except Exception as e:
                _logger.error(f"处理客户端请求时出错: {str(e)}")
                try:
                    error_response = {"status": "error", "message": str(e)}
                    client_socket.send(json.dumps(error_response).encode('utf-8'))
                except:
                    pass
                break
                
    finally:
        # 关闭客户端连接
        try:
            client_socket.close()
        except:
            pass
        _logger.info(f"客户端连接已关闭: {client_address}")

def start_server():
    """启动TCP服务器"""
    global _server_socket, _is_running, _logger

    # 启动串口服务
    if not start_serial_process():
        _logger.error("启动串口服务失败，服务器启动失败")

    try:
        # 创建TCP套接字
        _server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        _server_socket.bind((host, port))
        _server_socket.listen(max_connections)

        # 设置非阻塞模式
        _server_socket.settimeout(1.0)

        _is_running = True

        _logger.info(f"TCP服务器已启动，监听 {host}:{port}")

        while _is_running:
            try:
                # 接受客户端连接
                client_socket, client_address = _server_socket.accept()
                
                # 创建新线程处理客户端请求
                client_thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
                client_thread.daemon = True
                client_thread.start()
                time.sleep(1)

            except socket.timeout:
                # 接受连接超时，继续循环
                continue
            except Exception as e:
                if _is_running:
                    _logger.error(f"接受客户端连接时出错: {str(e)}")
                break

    except Exception as e:
        _logger.error(f"启动TCP服务器时出错: {str(e)}")
        return False

# @app.route('/send_data', methods=['POST'])
# def send():
#     """发送数据"""
#     data = request.json
#     slave_address = data['slave_address']
#     function_code = data['function_code']
#     start_address = data['start_address']
#     quantity = data['quantity']
#     send_data(slave_address, function_code, start_address, quantity)
#     return jsonify({'message': '数据发送成功'})

if __name__ == '__main__':
    _logger.info("正在启动串口TCP服务器...")
    
    if start_server():
        try:
            # 主线程保持运行
            while _is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            _logger.info("串口TCP服务器已退出") 
