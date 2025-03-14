"""
Modbus协议处理模块
用于处理Modbus协议帧的发送、接收和校验
"""
import time
import struct
import json
import sqlite3
import os
from datetime import datetime

class ModbusFrame:
    """Modbus帧对象类"""
    def __init__(self, slave_address=None, function_code=None, frame_bytes=None, hex_string=None):
        self.timestamp = datetime.now()
        self.id = int(time.time() * 1000)  # 毫秒级时间戳作为ID
        
        if frame_bytes:
            self.bytes = frame_bytes
        elif hex_string:
            self.bytes = self._hex_to_bytes(hex_string)
        else:
            self.bytes = []
            
        # 解析帧
        if self.bytes and len(self.bytes) >= 4:
            self.slave_address = self.bytes[0]
            self.function_code = self.bytes[1]
        else:
            self.slave_address = slave_address
            self.function_code = function_code
    
    def _hex_to_bytes(self, hex_string):
        """将十六进制字符串转换为字节列表"""
        hex_string = hex_string.replace(" ", "")
        return [int(hex_string[i:i+2], 16) for i in range(0, len(hex_string), 2)]
    
    def to_hex_string(self):
        """将字节列表转换为十六进制字符串"""
        return ''.join(['{:02x}'.format(b) for b in self.bytes])
    
    def to_dict(self):
        """转换为字典表示"""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'slaveAddress': self.slave_address,
            'functionCode': self.function_code,
            'frame': self.to_hex_string()
        }
    
    def is_valid(self):
        """验证帧的有效性（包括CRC校验）"""
        if len(self.bytes) < 4:  # 最小帧长度：地址(1) + 功能码(1) + CRC(2)
            return False
        
        return self._check_crc()
    
    def _check_crc(self):
        """验证CRC校验和"""
        if len(self.bytes) < 2:
            return False
        
        # 提取接收到的CRC（Modbus使用低字节在前的顺序）
        received_crc = (self.bytes[-1] << 8) | self.bytes[-2]
        
        # 计算CRC
        calc_crc = self._calculate_crc(self.bytes[:-2])
        
        return received_crc == calc_crc
    
    def _calculate_crc(self, data):
        """计算Modbus CRC-16"""
        crc = 0xFFFF
        
        for byte in data:
            crc ^= byte
            
            for _ in range(8):
                if crc & 0x0001:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        
        return crc


class ModbusResponseValidator:
    """Modbus响应验证器"""
    def __init__(self):
        self.buffer = bytearray()
        self.timeout = 1.0  # 响应超时时间（秒）
    
    def add_data(self, data):
        """添加接收到的数据到缓冲区"""
        if isinstance(data, bytes) or isinstance(data, bytearray):
            self.buffer.extend(data)
    
    def extract_response(self, request_frame):
        """从缓冲区中提取对应请求的响应帧"""
        if not self.buffer:
            return None
        
        # 基于请求帧寻找对应的响应
        slave_address = request_frame.slave_address
        function_code = request_frame.function_code
        
        # 检查缓冲区中是否有足够的数据
        if len(self.buffer) < 5:  # 最小响应长度：地址(1) + 功能码(1) + 至少1字节数据 + CRC(2)
            return None
        
        # 验证从站地址
        if self.buffer[0] != slave_address:
            return None
        
        # 验证功能码（注意错误响应会将功能码最高位置1）
        if self.buffer[1] != function_code and self.buffer[1] != (function_code | 0x80):
            return None
        
        # 对于不同的功能码，响应长度不同
        response_length = self._get_expected_response_length()
        
        if response_length > 0 and len(self.buffer) >= response_length:
            # 提取响应帧
            response_bytes = list(self.buffer[:response_length])
            self.buffer = self.buffer[response_length:]
            
            return ModbusFrame(frame_bytes=response_bytes)
        
        return None
    
    def _get_expected_response_length(self):
        """估计预期的响应长度"""
        if len(self.buffer) < 2:
            return 0
        
        function_code = self.buffer[1]
        
        # 错误响应: 地址(1) + 功能码(1) + 错误码(1) + CRC(2)
        if function_code & 0x80:
            return 5
        
        # 对于常见功能码的响应长度估计
        if function_code in (1, 2):  # 读线圈/输入
            if len(self.buffer) >= 3:
                byte_count = self.buffer[2]
                return 3 + byte_count + 2  # 地址(1) + 功能码(1) + 字节数(1) + 数据(n) + CRC(2)
        
        elif function_code in (3, 4):  # 读寄存器
            if len(self.buffer) >= 3:
                byte_count = self.buffer[2]
                return 3 + byte_count + 2  # 地址(1) + 功能码(1) + 字节数(1) + 数据(n) + CRC(2)
        
        elif function_code in (5, 6):  # 写单个线圈/寄存器
            return 8  # 地址(1) + 功能码(1) + 寄存器地址(2) + 值(2) + CRC(2)
        
        elif function_code in (15, 16):  # 写多个线圈/寄存器
            return 8  # 地址(1) + 功能码(1) + 起始地址(2) + 数量(2) + CRC(2)
        
        # 默认返回0，表示无法确定长度
        return 0
    
    def clear(self):
        """清除缓冲区"""
        self.buffer.clear()


class ModbusDatabase:
    """Modbus帧数据库管理"""
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        # 确保目录存在
        db_dir = os.path.dirname(self.db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建帧表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS modbus_frames (
            id INTEGER PRIMARY KEY,
            timestamp TEXT NOT NULL,
            slave_address INTEGER NOT NULL,
            function_code INTEGER NOT NULL,
            frame_type TEXT NOT NULL,
            request_id INTEGER,
            frame_data TEXT NOT NULL,
            error TEXT
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_frame(self, frame, frame_type='request', request_id=None, error=None):
        """保存Modbus帧到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO modbus_frames (
            id, timestamp, slave_address, function_code, frame_type, request_id, frame_data, error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            frame.id,
            frame.timestamp.isoformat(),
            frame.slave_address,
            frame.function_code,
            frame_type,
            request_id,
            frame.to_hex_string(),
            error
        ))
        
        conn.commit()
        conn.close()
        
        return frame.id
    
    def get_frame_by_id(self, frame_id):
        """根据ID获取帧"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT id, timestamp, slave_address, function_code, frame_type, request_id, frame_data, error
        FROM modbus_frames WHERE id = ?
        ''', (frame_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'timestamp': row[1],
                'slaveAddress': row[2],
                'functionCode': row[3],
                'type': row[4],
                'requestId': row[5],
                'frame': row[6],
                'error': row[7]
            }
        
        return None
    
    def get_response_for_request(self, request_id):
        """获取请求对应的响应"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT id, timestamp, slave_address, function_code, frame_type, request_id, frame_data, error
        FROM modbus_frames WHERE request_id = ? AND frame_type = 'response'
        ''', (request_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'timestamp': row[1],
                'slaveAddress': row[2],
                'functionCode': row[3],
                'type': row[4],
                'requestId': row[5],
                'frame': row[6],
                'error': row[7]
            }
        
        return None
    
    def get_frames(self, limit=50, offset=0):
        """获取帧列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT id, timestamp, slave_address, function_code, frame_type, request_id, frame_data, error
        FROM modbus_frames ORDER BY timestamp DESC LIMIT ? OFFSET ?
        ''', (limit, offset))
        
        rows = cursor.fetchall()
        conn.close()
        
        frames = []
        for row in rows:
            frames.append({
                'id': row[0],
                'timestamp': row[1],
                'slaveAddress': row[2],
                'functionCode': row[3],
                'type': row[4],
                'requestId': row[5],
                'frame': row[6],
                'error': row[7]
            })
        
        return frames
    
    def get_frames_by_time_range(self, start_time, end_time):
        """按时间范围获取帧"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT id, timestamp, slave_address, function_code, frame_type, request_id, frame_data, error
        FROM modbus_frames 
        WHERE timestamp BETWEEN ? AND ?
        ORDER BY timestamp DESC
        ''', (start_time, end_time))
        
        rows = cursor.fetchall()
        conn.close()
        
        frames = []
        for row in rows:
            frames.append({
                'id': row[0],
                'timestamp': row[1],
                'slaveAddress': row[2],
                'functionCode': row[3],
                'type': row[4],
                'requestId': row[5],
                'frame': row[6],
                'error': row[7]
            })
        
        return frames
    
    def clean_old_frames(self, max_entries):
        """清理旧的帧记录，保留最新的max_entries条"""
        if max_entries <= 0:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取总记录数
        cursor.execute('SELECT COUNT(*) FROM modbus_frames')
        total = cursor.fetchone()[0]
        
        if total > max_entries:
            # 计算需要删除的数量
            to_delete = total - max_entries
            
            # 获取要删除的ID列表
            cursor.execute('''
            SELECT id FROM modbus_frames ORDER BY timestamp ASC LIMIT ?
            ''', (to_delete,))
            
            ids_to_delete = [row[0] for row in cursor.fetchall()]
            
            # 删除这些记录
            placeholder = ','.join(['?'] * len(ids_to_delete))
            cursor.execute(f'DELETE FROM modbus_frames WHERE id IN ({placeholder})', ids_to_delete)
            
            conn.commit()
        
        conn.close() 