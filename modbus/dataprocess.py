import logging
from serial_serve import serial_manager
import os
import yaml
import sys

# 修改logger获取方式
logger = logging.getLogger('dataprocess')

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

# 使用配置
config = load_config()

retry_times = config['modbus']['retries']

def return_data_num(port_name):
    """返回指定串口的数据帧个数"""
    handler = serial_manager.serial_ports.get(port_name)
    if not handler:
        logger.error(f"未找到串口 {port_name} 的处理器")
        return 0
    return handler.receive_queue.length()

def send_data(port_name, slave_adress, function_code, start_address, quantity):
    """向指定串口发送数据"""
    port_logger = logging.getLogger(f"SerialPort_{port_name}")
    
    handler = serial_manager.serial_ports.get(port_name)
    if not handler:
        port_logger.error(f"未找到串口 {port_name} 的处理器")
        return False
        
    handler.send_queue.put((slave_adress, function_code, start_address, quantity))
    port_logger.info(f"向串口 {port_name} 发送数据: {slave_adress}, {function_code}, {start_address}, {quantity}")
    return True

def clear_receive_queue(port_name):
    """清空指定串口的接收队列"""
    handler = serial_manager.serial_ports.get(port_name)
    if not handler:
        logger.error(f"未找到串口 {port_name} 的处理器")
        return False
    handler.receive_queue.clear_queue()
    logger.info(f"串口 {port_name} 的接收队列已清空")
    return True


