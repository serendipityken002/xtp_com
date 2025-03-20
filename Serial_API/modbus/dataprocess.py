import logging
from serial_serve import _receive_queue, calculate_crc, _send_queue
import time
import threading

# 配置日志
logger = logging.getLogger(__name__)

def parse_response(response):
    """
    解析Modbus响应，此处为预设的解析流程
    """
    # 首先进行CRC校验
    crc = calculate_crc(response[:-2])
    if crc != response[-2:]:
        logger.warning(f"CRC校验失败: {response.hex()}")
        return None
    
    # 解析响应
    if response[1] == 0x03:
        mainOpen = (response[3] << 8) | response[4] == 0x0001
        LightOpen = (response[5] << 8) | response[6] == 0x0001
        fanRate = (response[7] << 8) | response[8]
        temperature = (response[9] << 8) | response[10]
        return mainOpen, LightOpen, fanRate, temperature
    else:
        logger.warning(f"{response.hex()} 不支持的解析")
        return None
    
def process_data_thread():
    """创建线程处理数据"""
    _process_thread = threading.Thread(target=process_data)
    _process_thread.daemon = True
    _process_thread.start()

    logger.info("接收队列数据处理线程已启动")

def process_data():
    """处理数据"""
    while True:
        data = _receive_queue.dequeue() # 从队列中获取一个数据
        if data:
            response = parse_response(data)
            logger.info(f"解析到的数据: {response}")
        else:
            time.sleep(0.5)

def send_data(slave_adress, function_code, start_address, quantity):
    """发送数据"""
    _send_queue.put((slave_adress, function_code, start_address, quantity))
    logger.info(f"send_data: {slave_adress}, {function_code}, {start_address}, {quantity}")
    return True
