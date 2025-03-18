import serial
import time
from threading import Thread

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
        """
        # 构建请求帧
        request = f'{slave_adress:02X} {function_code:02X} {start_address:04X} {quantity:04X}'
        request = bytes.fromhex(request)
        crc = calculate_crc(request)
        request += crc

        print(f"发送请求: {request.hex()}")
        self.serial.write(request)

        time.sleep(1)

        if self.serial.in_waiting > 0:
            response = self.serial.read(self.serial.in_waiting)
            print(f"收到响应: {response.hex()}")
            # CRC验证响应
            real_crc = calculate_crc(response[:-2])
            if real_crc == response[-2:]:
                print("CRC验证成功")
                # 解析响应
                mainOpen, LightOpen, fanRate, temperature = self.parse_response(response)
                print(f"主阀开: {mainOpen}, 灯开: {LightOpen}, 风扇速率: {fanRate}, 温度: {temperature}")
            else:
                print("CRC验证失败")
        else:
            print("没有收到响应")

    def parse_response(self, response):
        """
        解析Modbus响应
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

if __name__ == "__main__":
    client = ModbusClient('COM10')
    if client.connect():
        try:
            while True:
                print('===数据读取===\n')
                client.SendRequest(1, 3, 2, 4)
                client.SendRequest(2, 3, 2, 4)
                client.SendRequest(3, 3, 2, 4)

                choice = input('是否继续读取? (y/n): ')
                if choice.lower() != 'y':
                    break
        except Exception as e:
            print(f"发送失败: {e}")
        finally:
            client.serial.close()
