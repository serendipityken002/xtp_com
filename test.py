import serial
import time
import random
import struct
from threading import Thread


def calculate_crc(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc = crc >> 1
    # 返回低字节在前，高字节在后的CRC
    return crc.to_bytes(2, byteorder='little')

# ====== 主机程序类 ======
class ModbusClient:
    def __init__(self, port, baudrate=9600, timeout=1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial = None
        
    def connect(self):
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=self.timeout
            )
            print(f"已连接到串口 {self.port}")
            return True
        except Exception as e:
            print(f"连接错误: {e}")
            return False
            
    def disconnect(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
            print(f"已断开串口 {self.port}")
            
    def read_temperature(self, slave_address=1, register_address=0):
        """读取温度值 (Modbus功能码03 - 读保持寄存器)"""
        # 构建请求帧: 从站地址 + 功能码 + 寄存器地址 + 寄存器数量
        request = bytearray([
            slave_address,     # 从站地址
            0x03,              # 功能码 (03 = 读保持寄存器)
            register_address >> 8,  # 寄存器地址高字节
            register_address & 0xFF, # 寄存器地址低字节
            0x00,              # 寄存器数量高字节
            0x01               # 寄存器数量低字节 (读1个寄存器)
        ])
        
        # 计算并添加CRC
        crc = calculate_crc(request)
        request += crc
        
        try:
            # 清空接收缓冲区
            self.serial.reset_input_buffer()
            
            # 发送请求
            print(f"发送请求: {' '.join([f'{b:02X}' for b in request])}")
            self.serial.write(request)
            
            # 等待响应
            time.sleep(1)
            
            # 读取响应
            if self.serial.in_waiting > 0:
                response = self.serial.read(self.serial.in_waiting)
                print(f"收到响应: {' '.join([f'{b:02X}' for b in response])}")
                
                # 验证响应长度
                if len(response) >= 7:  # 最小长度检查
                    # 验证从站地址和功能码
                    if response[0] == slave_address and response[1] == 0x03:
                        # 验证CRC
                        response_data = response[:-2]
                        response_crc = response[-2:]
                        calculated_crc = calculate_crc(response_data)
                        
                        if response_crc == calculated_crc:
                            # 解析温度值 (使用两个字节的值)
                            temperature_raw = (response[3] << 8) | response[4]
                            # 转换为实际温度值 (假设是定点数，除以10得到实际温度)
                            temperature = temperature_raw / 10.0
                            return temperature
                        else:
                            print("CRC校验错误")
                    else:
                        print("响应地址或功能码错误")
                else:
                    print("响应帧长度不足")
            else:
                print("未收到响应")
                
        except Exception as e:
            print(f"通信错误: {e}")
            
        return None

# ====== 温度传感器模拟器类 ======
class TemperatureSensor:
    def __init__(self, port, slave_address=1, baudrate=9600):
        self.port = port
        self.slave_address = slave_address
        self.baudrate = baudrate
        self.serial = None
        self.running = False
        self.temperature = 25.0  # 初始温度值
        
    def connect(self):
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=1
            )
            print(f"传感器已连接到串口 {self.port}")
            return True
        except Exception as e:
            print(f"传感器连接错误: {e}")
            return False
            
    def disconnect(self):
        self.running = False
        if self.serial and self.serial.is_open:
            self.serial.close()
            print("传感器已断开连接")
            
    def update_temperature(self):
        """模拟温度变化"""
        self.temperature += random.uniform(-0.5, 0.5)
        # 限制温度范围在合理区间
        self.temperature = max(min(self.temperature, 40.0), 10.0)
        return self.temperature
        
    def start(self):
        """启动传感器监听线程"""
        if not self.serial or not self.serial.is_open:
            print("传感器未连接")
            return False
            
        self.running = True
        self.thread = Thread(target=self._listen)
        self.thread.daemon = True
        self.thread.start()
        print("传感器监听已启动")
        return True
        
    def _listen(self):
        """监听Modbus请求并响应"""
        while self.running:
            try:
                if self.serial.in_waiting > 0:
                    # 读取请求帧
                    request = self.serial.read(self.serial.in_waiting)
                    
                    if len(request) >= 8:  # Modbus RTU请求帧的最小长度
                        print(f"传感器收到请求: {' '.join([f'{b:02X}' for b in request])}")
                        
                        # 验证CRC
                        request_data = request[:-2]
                        request_crc = request[-2:]
                        calculated_crc = calculate_crc(request_data)
                        
                        if request_crc == calculated_crc:
                            # 验证从站地址
                            if request[0] == self.slave_address:
                                # 验证功能码
                                if request[1] == 0x03:  # 读保持寄存器
                                    # 获取寄存器地址和数量
                                    register_addr = (request[2] << 8) | request[3]
                                    register_count = (request[4] << 8) | request[5]
                                    
                                    # 检查请求的寄存器是否在有效范围内
                                    if register_addr <= 10 and register_count == 1:
                                        # 构建响应
                                        self.update_temperature()  # 更新温度值
                                        temp_int = int(self.temperature * 10)  # 转换为整数 (放大10倍)
                                        
                                        response = bytearray([
                                            self.slave_address,  # 从站地址
                                            0x03,               # 功能码
                                            0x02,               # 后续字节数 (2字节)
                                            temp_int >> 8,      # 温度高字节
                                            temp_int & 0xFF     # 温度低字节
                                        ])
                                        
                                        # 计算并添加CRC
                                        response_crc = calculate_crc(response)
                                        response += response_crc
                                        
                                        # 发送响应
                                        time.sleep(0.05)  # 模拟处理延时
                                        self.serial.write(response)
                                        print(f"传感器发送响应: {' '.join([f'{b:02X}' for b in response])}")
                                        print(f"当前温度: {self.temperature:.1f}°C")
                                    else:
                                        print("请求的寄存器无效")
                                else:
                                    print(f"不支持的功能码: {request[1]:02X}")
                            else:
                                print(f"从站地址不匹配: 请求={request[0]}, 传感器={self.slave_address}")
                        else:
                            print("请求CRC校验错误")
            except Exception as e:
                print(f"传感器处理错误: {e}")
                
            time.sleep(0.1)  # 避免CPU占用过高

# ====== 主程序 ======
def main():
    # 配置参数 (根据实际情况修改)
    MASTER_PORT = "COM10"  # 主机串口
    SENSOR_PORT = "COM11"  # 传感器串口
    SLAVE_ADDRESS = 1     # 传感器从站地址
    
    print("====== Modbus温度传感器通信系统 ======")
    print("1. 启动传感器模拟器")
    print("2. 启动主机程序")
    print("3. 退出")
    
    choice = input("请选择: ")
    
    if choice == "1":
        # 启动传感器模拟器
        sensor = TemperatureSensor(SENSOR_PORT, SLAVE_ADDRESS)
        if sensor.connect():
            sensor.start()
            print("传感器模拟器已启动，按Ctrl+C停止...")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                sensor.disconnect()
                
    elif choice == "2":
        # 启动主机程序
        client = ModbusClient(MASTER_PORT)
        if client.connect():
            try:
                while True:
                    print("\n===== 读取温度 =====")
                    temperature = client.read_temperature(SLAVE_ADDRESS)
                    if temperature is not None:
                        print(f"当前温度: {temperature:.1f}°C")
                    else:
                        print("读取温度失败")
                        
                    choice = input("继续读取? (y/n): ")
                    if choice.lower() != 'y':
                        break
            finally:
                client.disconnect()
    
    elif choice == "3":
        pass
    
    else:
        print("无效选择")
        
    print("程序已退出")

if __name__ == "__main__":
    main()
