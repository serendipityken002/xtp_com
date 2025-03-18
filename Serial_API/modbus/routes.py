from flask import Blueprint, request, jsonify
import os
import yaml

import serial
import time
from threading import Thread, Lock
from concurrent.futures import ThreadPoolExecutor, as_completed

# 加载配置文件
config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
with open(config_path, 'r', encoding='utf-8') as file:
    config = yaml.safe_load(file)

# 使用配置
host = config['server']['host']
port = config['server']['port']
debug = config['server']['debug']

port_name = config['default_serial_config']['port_name']
baudrate_default = config['default_serial_config']['baudrate']
timeout_default = config['default_serial_config']['timeout']
max_length = config['max_entries']

response_timeout = config['modbus']['response_timeout']
retries = config['modbus']['retries']
max_workers = config['max_workers']

# ====== Modbus CRC计算函数 ======
def calculate_crc(data):
    """
    crc初始为0xFFFF，遍历data的每个字节，与crc异或运算作为新的crc
    - 如果crc的最低位为1，则将crc右移1位，并异或0xA001
    - 否则，将crc右移1位
    - 最后返回低字节在前，高字节在后的CRC
    """
    crc = 0xffff
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc = crc >> 1
    return crc.to_bytes(2, byteorder='little')

# ====== 主机程序类 ======
class ModbusClient:
    def __init__(self, port, baudrate=baudrate_default, timeout=timeout_default):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial = None

    def connect(self):
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            print(f"成功连接到{self.port}，波特率{self.baudrate}")
            return True
        except Exception as e:
            print(f"连接失败: {e}")
            return False

    def SendRequest(self, slave_adress, function_code, start_address, quantity):
        """
        发送Modbus请求
        param: slave_adress, function_code, start_address, quantity
        return: mainOpen, LightOpen, fanRate, temperature
        """
        # 构建请求帧
        request = f'{slave_adress:02X} {function_code:02X} {start_address:04X} {quantity:04X}'
        request = bytes.fromhex(request)
        crc = calculate_crc(request)
        request += crc

        for i in range(retries):
            print(f"第 {i+1} 次发送请求: {request.hex()}")
            self.serial.write(request)

            time.sleep(response_timeout)

            if self.serial.in_waiting > 0:
                response = self.serial.read(self.serial.in_waiting)
                print(f"收到响应: {response.hex()}")
                # CRC验证响应
                real_crc = calculate_crc(response[:-2])
                if real_crc == response[-2:]:

                    # 解析响应
                    mainOpen, LightOpen, fanRate, temperature = self.parse_response(response)
                    print(f"主阀开: {mainOpen}, 灯开: {LightOpen}, 风扇速率: {fanRate}, 温度: {temperature}")
                    return mainOpen, LightOpen, fanRate, temperature
                else:
                    print("CRC验证失败")
            else:
                print("没有收到响应")
        return None

    def parse_response(self, response):
        """
        解析Modbus响应，此处为预设的解析流程
        """
        if response[1] == 0x03 and self.port == 'COM10':
            mainOpen = (response[3] << 8) | response[4] == 0x0001
            LightOpen = (response[5] << 8) | response[6] == 0x0001
            fanRate = (response[7] << 8) | response[8]
            temperature = (response[9] << 8) | response[10]
            return mainOpen, LightOpen, fanRate, temperature
        else:
            print("不支持的解析")
            return None

def process_single_request(modbus_client, request_params):
    """处理单个Modbus请求的函数"""
    try:
        slave_address = request_params.get('slave_address')
        function_code = request_params.get('function_code')
        start_address = request_params.get('start_address')
        quantity = request_params.get('quantity')

        result = modbus_client.SendRequest(slave_address, function_code, start_address, quantity)

        return {
            'slave_address': slave_address,
            'status': 'success',
            'data': result,
            'error': None
        }
    except Exception as e:
        return {
            'slave_address': slave_address,
            'status': 'error',
            'data': None,
            'error': str(e)
        }

# 全局ModbusClient实例和锁
global_modbus_client = None
client_lock = Lock()

def get_modbus_client(port_name):
    """获取或创建ModbusClient实例的单例模式"""
    global global_modbus_client
    
    with client_lock:
        if global_modbus_client is None:
            global_modbus_client = ModbusClient(port_name)
            global_modbus_client.connect()
        elif global_modbus_client.port != port_name:
            # 如果端口变化，重新连接
            global_modbus_client = ModbusClient(port_name)
            global_modbus_client.connect()
    
    return global_modbus_client

modbus_bp = Blueprint('modbus', __name__)

@modbus_bp.route('/send', methods=['POST'])
def send_modbus_frame():
    try:
        data = request.json
        requests_list = data.get('requests', [])
        port_name = data.get('port_name')
        
        if not requests_list:
            return jsonify({
                'status': 'error',
                'message': '没有收到请求列表'
            }), 400

        # 获取或创建ModbusClient实例
        get_modbus_client(port_name)

        results = []

        # 一个个发送
        for request_params in requests_list:
            result = process_single_request(global_modbus_client, request_params)
            results.append(result)

        return jsonify({
            'status': 'success',
            'results': results,
        })
    
        # # 使用线程池处理请求
        # with ThreadPoolExecutor(max_workers=min(max_workers, len(requests_list))) as executor:
        #     # 创建future对象列表
        #     future_to_request = {
        #         executor.submit(
        #             process_single_request,
        #             global_modbus_client,
        #             request_params
        #         ): request_params
        #         for request_params in requests_list
        #     }

        #     # 收集所有请求的结果
        #     for future in as_completed(future_to_request):
        #         result = future.result()
        #         results.append(result)

        #     return jsonify({
        #         'status': 'success',
        #         'results': results,
        #         'total_requests': len(requests_list),
        #         'successful_requests': sum(1 for r in results if r['status'] == 'success'),
        #         'failed_requests': sum(1 for r in results if r['status'] == 'error')
        #     })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'处理请求时发生错误: {str(e)}'
        }), 500

