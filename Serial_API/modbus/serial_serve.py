# 配置串口连接，定义接收和发送函数

import serial
import yaml
import threading
import time
import queue
import logging
import os
from collections import deque

# 加载配置文件
config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
with open(config_path, 'r', encoding='utf-8') as file:
    config = yaml.safe_load(file)

# 获取配置
log_file = config['logging']['filename']
log_mode = config['logging']['filemode']

port_default = config['default_serial_config']['port_name']
baudrate_default = config['default_serial_config']['baudrate']
timeout_default = config['default_serial_config']['timeout']
max_length = config['max_entries']

# 配置日志
logger = logging.getLogger(__name__)

class CircularQueue:
    """循环队列实现，用于存储串口接收到的数据"""
    def __init__(self, max_size = max_length):
        self.queue = deque(maxlen=max_size)
        self.max_size = max_size
        self.lock = threading.Lock()
        self.is_full = False  # 标记队列是否已满
        self.has_overflowed = False  # 标记是否发生过覆盖

    def enqueue(self, data):
        """数据入队"""
        with self.lock:
            # 检查是否会溢出
            will_overflow = len(self.queue) + len(data) > self.max_size

            if will_overflow:
                self.has_overflowed = True
                logger.warning(f"接收队列已满 (大小: {self.max_size} 字节)，开始覆盖最早的数据")

            self.queue.append(data)

            return True
        
    def dequeue(self):
        """取出最早的数据"""
        with self.lock:
            if len(self.queue) == 0:
                return None
            return self.queue.popleft()

    def length(self):
        """获取队列长度"""
        with self.lock:
            return len(self.queue)

# 全局变量
_serial_port = None
_is_connected = False
_send_queue = queue.Queue()
_receive_queue = CircularQueue()
_send_thread = None
_receive_thread = None


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

def connect_serial(port_name = port_default):
    """连接串口"""
    global _serial_port, _is_connected
    try:
        if _is_connected:
            logger.warning(f"串口{port_name}已连接，无需重复连接")
            return True
        _serial_port = serial.Serial(
            port = port_name,
            baudrate = baudrate_default,
            timeout = timeout_default
        )
        _is_connected = True
        logger.info(f"成功连接到{port_name}，波特率{baudrate_default}")
        return True
    except Exception as e:
        logger.error(f"串口{port_name}连接失败: {e}")
        _is_connected = False
        return False
    
def disconnect_serial(port_name):
    """断开串口"""
    global _serial_port, _is_connected
    try:
        if _is_connected:
            _serial_port.close()
            _is_connected = False
        logger.info(f"成功断开串口{port_name}")
        return True
    except Exception as e:
        logger.error(f"断开串口{port_name}失败: {e}")
        _is_connected = True
        return False
        
def send_data(slave_adress, function_code, start_address, quantity):
    """
    发送Modbus请求
    param: slave_adress, function_code, start_address, quantity
    return: mainOpen, LightOpen, fanRate, temperature
    """
    global _serial_port, _is_connected
    if not _is_connected:
        logger.warning("串口未连接，无法发送数据")
        return False
    
    # 构建请求帧
    request = f'{slave_adress:02X} {function_code:02X} {start_address:04X} {quantity:04X}'
    request = bytes.fromhex(request)
    crc = calculate_crc(request)
    request += crc

    try:
        _serial_port.write(request)
        logger.info(f"成功发送请求: {request.hex()}")
        return True
    except Exception as e:
        logger.error(f"发送请求失败: {e}")
        return False

def _send_task():
    """发送数据线程"""
    global _send_queue, _is_connected

    logger.info("串口发送线程已启动")
    while _is_connected:
        try:
            # 从队列中获取数据
            data = _send_queue.get(timeout=1)
            slave_adress, function_code, start_address, quantity = data
            send_data(slave_adress, function_code, start_address, quantity)
            time.sleep(1)
        except queue.Empty:
            pass
        except Exception as e:
            logger.error(f"发送数据线程错误: {e}")
            time.sleep(1)

    logger.info("串口发送线程已停止")

def _receive_task():
    """接收数据线程"""
    global _receive_queue, _is_connected

    logger.info("串口接收线程已启动")
    while _is_connected:
        try:
            # 从串口读取数据
            if _serial_port.in_waiting > 0:
                data = _serial_port.read(_serial_port.in_waiting)
                if data:
                    _receive_queue.enqueue(data)
                    logger.info(f"接收到的数据: {data.hex()}")
                else:
                    time.sleep(0.1)
            time.sleep(1)
        except Exception as e:
            logger.error(f"接收数据线程错误: {e}")
            time.sleep(1)

    logger.info("串口接收线程已停止")


def start_serial_process(com = port_default):
    global _is_connected, _receive_thread, _send_thread, _receive_queue

    # 连接串口
    if not connect_serial(com):
        logger.error(f"串口{com}连接失败")
        return False
    
    # 启动接收线程
    _receive_thread = threading.Thread(target=_receive_task)
    _receive_thread.daemon = True
    _receive_thread.start()
    
    # 启动发送线程
    _send_thread = threading.Thread(target=_send_task)
    _send_thread.daemon = True
    _send_thread.start()
    
    logger.info("串口服务已启动")
    
    return True
    
