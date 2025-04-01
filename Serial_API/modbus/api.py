from flask import Flask, request, jsonify
from flask_cors import CORS
from dataprocess import send_data, return_data_num, clear_receive_queue
from serial_serve import start_serial_process, serial_manager, get_complete_frames
import socket
import yaml
import time
import logging
from logging.config import dictConfig
from datetime import datetime
import os
import threading
import json
import sys

app = Flask(__name__)
CORS(app)

def load_config():
    # 首先尝试读取外部配置文件
    external_config = 'config.yaml'  # 与可执行文件同目录的配置文件
    if os.path.exists(external_config):
        with open(external_config, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    
    # 如果外部配置不存在，则使用打包的配置
    if getattr(sys, 'frozen', False):
        # 运行在打包环境
        base_path = sys._MEIPASS
    else:
        # 运行在开发环境
        base_path = os.path.dirname(__file__)
    
    config_path = os.path.join(base_path, 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

# 首先加载配置
config = load_config()

# 然后定义日志相关的类和函数
def get_log_file_paths(port_name=None):
    """获取当前的日志文件路径"""
    log_dir = 'logs'
    
    if port_name:
        # 串口特定的日志目录
        base_dir = os.path.join(log_dir, f'serial_{port_name}')
    else:
        # 主程序的日志目录
        base_dir = log_dir
        
    error_log_dir = os.path.join(base_dir, 'wrong_log')
    print_log_dir = os.path.join(base_dir, 'print_log')
    warning_log_dir = os.path.join(base_dir, 'warning_log')

    # 确保目录存在
    for dir_path in [base_dir, error_log_dir, print_log_dir, warning_log_dir]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

    today_str = datetime.now().strftime('%Y-%m-%d')
    error_today_dir = os.path.join(error_log_dir, today_str)
    print_today_dir = os.path.join(print_log_dir, today_str)
    warning_today_dir = os.path.join(warning_log_dir, today_str)

    # 确保当天的目录存在
    for dir_path in [error_today_dir, print_today_dir, warning_today_dir]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

    time_now = datetime.now().strftime('%H')
    error_log_file = os.path.join(error_today_dir, f'error_{time_now}.txt')
    print_log_file = os.path.join(print_today_dir, f'info_{time_now}.log')
    warning_log_file = os.path.join(warning_today_dir, f'warning_{time_now}.log')

    return error_log_file, print_log_file, warning_log_file

class TimedRotatingHandler(logging.Handler):
    """自定义处理程序，支持按时间更新日志文件"""
    def __init__(self, get_filename_func, mode='a', encoding='utf-8'):
        super().__init__()
        self.get_filename_func = get_filename_func
        self.mode = mode
        self.encoding = encoding
        self.current_filename = None
        self.current_file = None
        self.last_time = None

    def emit(self, record):
        try:
            current_time = datetime.now().strftime('%Y-%m-%d-%H')
            
            # 检查是否需要更换文件
            if current_time != self.last_time:
                if self.current_file:
                    self.current_file.close()
                self.current_filename = self.get_filename_func()
                self.current_file = open(self.current_filename, self.mode, encoding=self.encoding)
                self.last_time = current_time

            msg = self.format(record)
            self.current_file.write(msg + '\n')
            self.current_file.flush()
        except Exception:
            self.handleError(record)

def setup_logging():
    """设置日志配置"""
    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': True,  # 修改为True，防止日志传播
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
        },
        'loggers': {
            '': {  # root logger
                'handlers': ['console'],
                'level': 'DEBUG',
                'propagate': False  # 修改为False
            },
        }
    }

    # 添加主程序的日志处理器
    LOGGING_CONFIG['handlers'].update({
        'main_error_file': {
            'class': '__main__.TimedRotatingHandler',
            'level': 'ERROR',
            'formatter': 'standard',
            'get_filename_func': lambda: get_log_file_paths()[0],
        },
        'main_print_file': {
            'class': '__main__.TimedRotatingHandler',
            'level': 'DEBUG',
            'formatter': 'standard',
            'get_filename_func': lambda: get_log_file_paths()[1],
        },
        'main_warning_file': {
            'class': '__main__.TimedRotatingHandler',
            'level': 'WARNING',
            'formatter': 'standard',
            'get_filename_func': lambda: get_log_file_paths()[2],
        },
    })

    # 为每个串口添加日志处理器
    serial_ports = config.get('serial_ports', [])
    for port_config in serial_ports:
        port_name = port_config.get('name')
        if port_name:
            # 为每个串口创建独立的处理器
            port_handlers = {
                f'{port_name}_error_file': {
                    'class': '__main__.TimedRotatingHandler',
                    'level': 'ERROR',
                    'formatter': 'standard',
                    'get_filename_func': lambda p=port_name: get_log_file_paths(p)[0],
                },
                f'{port_name}_print_file': {
                    'class': '__main__.TimedRotatingHandler',
                    'level': 'DEBUG',
                    'formatter': 'standard',
                    'get_filename_func': lambda p=port_name: get_log_file_paths(p)[1],
                },
                f'{port_name}_warning_file': {
                    'class': '__main__.TimedRotatingHandler',
                    'level': 'WARNING',
                    'formatter': 'standard',
                    'get_filename_func': lambda p=port_name: get_log_file_paths(p)[2],
                }
            }
            LOGGING_CONFIG['handlers'].update(port_handlers)
            
            # 为每个串口创建独立的logger
            LOGGING_CONFIG['loggers'][f'SerialPort_{port_name}'] = {
                'handlers': ['console'] + [f'{port_name}_{level}_file' for level in ['error', 'print', 'warning']],
                'level': 'DEBUG',
                'propagate': False  # 确保不传播到root logger
            }

    # 更新主程序的logger配置
    LOGGING_CONFIG['loggers']['__main__'] = {
        'handlers': ['console', 'main_error_file', 'main_print_file', 'main_warning_file'],
        'level': 'DEBUG',
        'propagate': False
    }

    # 更新dataprocess的logger配置
    LOGGING_CONFIG['loggers']['dataprocess'] = {
        'handlers': ['console', 'main_error_file', 'main_print_file', 'main_warning_file'],
        'level': 'DEBUG',
        'propagate': False
    }

    dictConfig(LOGGING_CONFIG)

# 最后设置日志
setup_logging()

# 设置全局变量
_server_socket = None
_is_running = False
_logger = logging.getLogger(__name__)

# 从配置中获取服务器参数
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
                    port_name = request.get('port')  # 获取串口名称

                    if not data_to_send:
                        response = {"status": "error", "message": "缺少data参数"}
                    elif not port_name:
                        response = {"status": "error", "message": "缺少port参数"}
                    else:
                        slave_adress = data_to_send[0]
                        function_code = data_to_send[1]
                        start_address = data_to_send[2]
                        quantity = data_to_send[3]
                        success = send_data(port_name, slave_adress, function_code, start_address, quantity)
                        if success:
                            response = {"status": "success", "message": f"成功发送数据到串口 {port_name}: {data_to_send}"}
                        else:
                            response = {"status": "error", "message": f"发送数据到串口 {port_name} 失败: {data_to_send}"}
                            
                elif request.get('action') == 'receive':
                    # 接收数据
                    num = request.get('num')
                    port_name = request.get('port')
                    
                    if not num:
                        response = {"status": "error", "message": "缺少num参数"}
                    elif not port_name:
                        response = {"status": "error", "message": "缺少port参数"}
                    else:
                        handler = serial_manager.serial_ports.get(port_name)
                        if not handler:
                            response = {"status": "error", "message": f"未找到串口 {port_name} 的处理器"}
                        else:
                            try:
                                port_logger = logging.getLogger(f"SerialPort_{port_name}")
                                frames = get_complete_frames(handler.receive_queue, port_logger, num)
                                
                                if frames:
                                    response = {
                                        "status": "success",
                                        "frames": frames,
                                        "port": port_name
                                    }
                                else:
                                    response = {
                                        "status": "success",
                                        "frames": [],
                                        "port": port_name
                                    }
                                    
                            except Exception as e:
                                _logger.error(f"读取数据帧时出错: {str(e)}")
                                response = {"status": "error", "message": str(e)}

                elif request.get('action') == 'queue_size':
                    # 获取队列大小
                    port_name = request.get('port')  # 获取串口名称
                    
                    if not port_name:
                        response = {"status": "error", "message": "缺少port参数"}
                    else:
                        size = return_data_num(port_name)
                        _logger.info(f"串口 {port_name} 当前剩余数据帧个数：{size}")
                        response = {"status": "success", "size": size, "port": port_name}
                    
                elif request.get('action') == 'clear_queue':
                    # 清空接收队列
                    port_name = request.get('port')  # 获取串口名称
                    
                    if not port_name:
                        response = {"status": "error", "message": "缺少port参数"}
                    else:
                        clear_receive_queue(port_name)
                        response = {"status": "success", "message": f"串口 {port_name} 的接收队列已清空"}

                elif request.get('action') == 'status':
                    # 获取所有串口状态
                    ports_status = {}
                    for port_name in serial_manager.serial_ports:
                        handler = serial_manager.serial_ports[port_name]
                        ports_status[port_name] = {
                            "connected": handler.is_connected,
                            "queue_size": handler.receive_queue.length()
                        }
                    response = {
                        "status": "success", 
                        "server_running": _is_running,
                        "ports": ports_status
                    }

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

    # 启动多个串口服务
    serial_ports = config.get('serial_ports', [])
    if not serial_ports:
        _logger.error("未找到串口配置信息")
        return False

    # 尝试启动所有配置的串口
    success_count = 0
    for port_config in serial_ports:
        port_name = port_config.get('name')
        baudrate = port_config.get('baudrate')
        
        if not port_name or not baudrate:
            _logger.error(f"串口配置信息不完整: {port_config}")
            continue
            
        try:
            if start_serial_process(com=port_name, baudrate=baudrate):
                _logger.info(f"成功启动串口 {port_name}, 波特率 {baudrate}")
                success_count += 1
            else:
                _logger.error(f"启动串口失败: {port_name}")
        except Exception as e:
            _logger.error(f"启动串口 {port_name} 时发生错误: {str(e)}")

    if success_count == 0:
        _logger.error("所有串口启动失败，服务器启动失败")
        return False
    else:
        _logger.info(f"成功启动 {success_count} 个串口")

    try:
        # 创建TCP套接字
        _server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # 创建TCP套接字
        _server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # 设置套接字选项，允许重用地址
        _server_socket.bind((host, port)) # 绑定地址和端口
        _server_socket.listen(max_connections) # 设置最大连接数

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
