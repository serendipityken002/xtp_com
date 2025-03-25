# 配置串口连接，定义接收和发送函数

import serial
import yaml
import threading
import time
import queue
import logging
import os
from collections import deque
import sys

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

config = load_config()

# # 加载配置文件
# config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
# with open(config_path, 'r', encoding='utf-8') as file:
#     config = yaml.safe_load(file)

port_default = config['default_serial_config']['port_name']
baudrate_default = config['default_serial_config']['baudrate']
timeout_default = config['default_serial_config']['timeout']
max_length = config['tcp_server']['buffer_size']

# 配置日志
logger = logging.getLogger(__name__)

def get_complete_frames(receive_queue, port_logger, number_of_frames):
    """获取完整的Modbus帧
    Args:
        receive_queue: 接收队列
        port_logger: 串口日志记录器
        number_of_frames: 需要读取的帧数
    Returns:
        list: 完整帧的列表，每个元素为十六进制字符串
    """
    frames = []
    temp_bytes = []
    frame_size = 0
    collecting = False
    retry = 0

    if receive_queue.length() < 3:
        port_logger.warning(f"数据不足，当前队列长度: {receive_queue.length()} 字节")
        return None

    while len(frames) < number_of_frames:
        try:
            if not collecting:
                # 读取前3个字节
                if receive_queue.length() < 3:
                    break
                    
                for _ in range(3):
                    byte_data = receive_queue.dequeue()
                    temp_bytes.append(byte_data)
                    
                # 计算完整帧大小
                data_length = temp_bytes[2]
                frame_size = 2 + 1 + data_length + 2
                collecting = True
                
            # 继续收集剩余字节
            remaining_bytes = frame_size - len(temp_bytes)
            if receive_queue.length() < remaining_bytes:
                break
            
            for _ in range(remaining_bytes):
                byte_data = receive_queue.dequeue()
                temp_bytes.append(byte_data)
            
            # 组合完整帧
            if len(temp_bytes) == frame_size:
                frame_data = bytes(temp_bytes)
                frames.append(frame_data.hex())
                temp_bytes = []
                frame_size = 0
                collecting = False
                
        except Exception as e:
            port_logger.error(f"获取完整帧时出错: {e}")
            retry += 1
            if retry >= config['modbus']['retries']:
                port_logger.error("重试次数过多，停止读取")
                break
            temp_bytes = []
            frame_size = 0
            collecting = False

    return frames

class CircularQueue:
    """循环队列实现，用于存储串口接收到的数据"""
    def __init__(self, max_size=max_length):
        self.queue = deque(maxlen=max_size)
        self.max_size = max_size
        self.lock = threading.Lock()
        self.is_full = False
        self.has_overflowed = False
        self.overflow_count = 0
        self.paused = False  # 添加暂停标志
        self.logger = logging.getLogger(__name__)
        
    def enqueue(self, data):
        """数据入队"""
        with self.lock:
            # 如果队列已满或已暂停，拒绝写入数据
            if self.paused:
                return False
                
            if len(self.queue) >= self.max_size:
                self.has_overflowed = True
                self.overflow_count += 1
                self.paused = True  # 暂停接收
                
                # 记录日志
                self.logger.warning(
                    f"接收队列第 {self.overflow_count} 次溢出，队列已满，暂停接收新数据"
                )
                
                # 返回False表示未写入数据
                return False
                
            # 正常情况，添加数据
            self.queue.append(data)
            return True
            
    def process_full_queue(self, port_logger):
        """处理满队列中的所有完整帧"""
        if not self.paused:
            return
            
        try:
            # 循环处理队列中的所有完整帧
            frames_processed = 0
            max_frames = 50  # 最多处理50个帧，避免处理太久
            
            while frames_processed < max_frames:
                frames = get_complete_frames(self, port_logger, 1)  # 每次处理一个完整帧
                if not frames:
                    break  # 没有更多完整帧了
                    
                for frame in frames:
                    # 记录已处理的帧
                    port_logger.warning(f"队列满，自动处理帧: {frame}")
                    frames_processed += 1
            
            # 记录处理结果
            if frames_processed > 0:
                port_logger.warning(f"队列满处理完成: 已处理 {frames_processed} 个完整帧")
            else:
                port_logger.warning("队列满但未找到完整帧")
                
            # 重置暂停状态
            with self.lock:
                self.paused = False
                port_logger.info("已恢复接收新数据")
                
        except Exception as e:
            port_logger.error(f"处理满队列时出错: {e}")
            # 确保恢复接收状态
            with self.lock:
                self.paused = False
                
    def is_paused(self):
        """检查队列是否暂停接收"""
        return self.paused
        
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
        
    def clear_queue(self):
        """清空队列"""
        with self.lock:
            self.queue.clear()
            self.paused = False  # 清空队列后恢复接收

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

class SerialManager:
    """串口管理类，用于管理多个串口连接"""
    def __init__(self):
        self.serial_ports = {}  # 存储所有串口对象 {port_name: SerialHandler}
        
class SerialHandler:
    """单个串口处理类"""
    def __init__(self, port_name, baudrate, timeout=1):
        self.port_name = port_name
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_port = None
        self.is_connected = False
        self.receive_queue = CircularQueue()
        self.send_queue = queue.Queue()
        self.receive_thread = None
        self.send_thread = None
        # 添加临时缓冲区用于存储被拒绝的数据
        self.temp_buffer = bytearray()
        # 使用独立的logger
        self.logger = logging.getLogger(f"SerialPort_{self.port_name}")
        # 确保该logger不会传播到父logger
        self.logger.propagate = False
        
    def connect(self):
        """连接串口"""
        try:
            if self.is_connected:
                self.logger.warning(f"串口{self.port_name}已连接，无需重复连接")
                return True
                
            self.serial_port = serial.Serial(
                port=self.port_name,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            self.is_connected = True
            self.logger.info(f"成功连接到{self.port_name}，波特率{self.baudrate}")
            
            # 启动收发线程
            self._start_threads()
            return True
            
        except Exception as e:
            self.logger.error(f"串口{self.port_name}连接失败: {e}")
            self.is_connected = False
            return False
            
    def _start_threads(self):
        """启动收发线程"""
        self.receive_thread = threading.Thread(
            target=self._receive_task, 
            name=f"Receive_{self.port_name}"
        )
        self.receive_thread.daemon = True
        self.receive_thread.start()
        
        self.send_thread = threading.Thread(
            target=self._send_task, 
            name=f"Send_{self.port_name}"
        )
        self.send_thread.daemon = True
        self.send_thread.start()

    def _receive_task(self):
        """接收数据线程"""
        self.logger.info(f"串口{self.port_name}接收线程已启动")
        
        while self.is_connected:
            try:
                # 检查队列是否暂停接收
                if self.receive_queue.is_paused():
                    # 队列已满，处理队列中的完整帧
                    self.logger.info("接收队列已满，开始处理队列中的数据")
                    self.receive_queue.process_full_queue(self.logger)
                    
                    # 尝试写入临时缓冲区中的数据
                    if self.temp_buffer and not self.receive_queue.is_paused():
                        self._process_temp_buffer()
                    
                    continue  # 处理完后重新检查串口
                
                # 先处理临时缓冲区中的数据
                if self.temp_buffer and not self.receive_queue.is_paused():
                    self._process_temp_buffer()
                
                # 正常接收数据
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    if data:
                        # 直接尝试将数据添加到临时缓冲区，然后处理
                        self.temp_buffer.extend(data)
                        self.logger.info(f"接收到的数据: {data.hex()}, 共 {len(data)} 字节")
                        
                        # 处理临时缓冲区数据
                        self._process_temp_buffer()
                else:
                    time.sleep(config['serial']['receive_time'])
            except Exception as e:
                self.logger.error(f"接收数据线程错误: {e}")
                time.sleep(config['serial']['receive_error_time'])
    
    def _process_temp_buffer(self):
        """处理临时缓冲区中的数据"""
        if not self.temp_buffer:
            return
            
        successful_writes = 0
        remaining_bytes = bytearray()
        
        # 尝试将临时缓冲区中的数据写入队列
        for byte_data in self.temp_buffer:
            if self.receive_queue.is_paused():
                # 队列再次满了，保留剩余数据
                remaining_bytes.append(byte_data)
            elif self.receive_queue.enqueue(byte_data):
                successful_writes += 1
            else:
                # 队列刚刚满了，保留剩余数据
                remaining_bytes.append(byte_data)
        
        # 更新临时缓冲区为未写入的数据
        self.temp_buffer = remaining_bytes
        
        # 记录处理结果
        if successful_writes > 0:
            self.logger.info(f"从临时缓冲区写入 {successful_writes} 字节数据")
        if self.temp_buffer:
            self.logger.warning(f"临时缓冲区仍有 {len(self.temp_buffer)} 字节等待处理")

    def _send_task(self):
        """发送数据线程"""
        self.logger.info(f"串口{self.port_name}发送线程已启动")
        while self.is_connected:
            try:
                data = self.send_queue.get(timeout=1)
                slave_adress, function_code, start_address, quantity = data
                self.send_data(slave_adress, function_code, start_address, quantity)
                time.sleep(config['serial']['send_time'])
            except queue.Empty:
                pass
            except Exception as e:
                self.logger.error(f"发送数据线程错误: {e}")
                time.sleep(config['serial']['send_error_time'])

    def send_data(self, slave_adress, function_code, start_address, quantity):
        """发送Modbus请求"""
        if not self.is_connected:
            self.logger.warning("串口未连接，无法发送数据")
            return False
            
        request = f'{int(slave_adress):02x} {int(function_code):02x} {int(start_address):04x} {int(quantity):04x}'
        request = bytes.fromhex(request)
        crc = calculate_crc(request)
        request += crc
        
        try:
            self.serial_port.write(request)
            self.logger.info(f"成功发送请求: {request.hex()}")
            return True
        except Exception as e:
            self.logger.error(f"发送请求失败: {e}")
            return False

    def disconnect(self):
        """断开串口连接"""
        try:
            if self.is_connected:
                self.is_connected = False
                self.serial_port.close()
            self.logger.info(f"成功断开串口{self.port_name}")
            return True
        except Exception as e:
            self.logger.error(f"断开串口{self.port_name}失败: {e}")
            return False

# 创建全局串口管理器实例
serial_manager = SerialManager()

def start_serial_process(com, baudrate, timeout=1):
    """启动串口服务"""
    handler = SerialHandler(com, baudrate, timeout)
    if handler.connect():
        serial_manager.serial_ports[com] = handler
        return True
    return False
    
