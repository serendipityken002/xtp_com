import logging
from serial_serve import _receive_queue, calculate_crc, _send_queue
import time
import threading
from queue import Empty

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

def process_data(number_of_items):
    """处理指定个数的数据"""
    processed_count = 0
    total_response = None
    
    while processed_count < number_of_items:
        try:
            data = _receive_queue.dequeue()  # 尝试从队列中获取数据，设置超时避免无限等待
            if data:
                response = parse_response(data)
                logger.info(f"解析到的数据: {response}")
                total_response += response
                processed_count += 1  # 只有当成功处理了数据时才增加计数
        except Empty:
            # 如果在0.5秒内没有获取到数据，则继续循环尝试直到处理完指定数量的数据
            if _receive_queue.empty() and processed_count >= _receive_queue.length():
                logger.warning("数据帧全部取出")
                break
            continue
    return total_response

def return_data_num():
    """返回数据帧个数"""
    return _receive_queue.length()

def send_data(slave_adress, function_code, start_address, quantity):
    """发送数据"""
    _send_queue.put((slave_adress, function_code, start_address, quantity))
    logger.info(f"send_data: {slave_adress}, {function_code}, {start_address}, {quantity}")
    return True
