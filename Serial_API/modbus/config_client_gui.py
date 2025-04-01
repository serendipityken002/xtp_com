from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QGroupBox, QSpinBox, QComboBox, QTextEdit, QTabWidget, 
                           QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
import yaml
import sys
import os
import socket
import json

class ConfigClientGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('串口服务器配置与控制')
        self.setGeometry(100, 100, 800, 600)
        
        # 设置全局字体
        app = QApplication.instance()
        font = QFont()
        font.setPointSize(12)  # 设置字体大小
        app.setFont(font)
        
        # 添加连接状态和定时器
        self.is_connected = False
        self.client_socket = None
        self.is_continuous_sending = False
        self.send_timer = QTimer()
        self.send_timer.timeout.connect(self.send_client_request)

        # 创建套接字
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.settimeout(5.0)

        # 创建主widget和布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # 创建标签页
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # 配置页
        config_widget = QWidget()
        config_layout = QVBoxLayout(config_widget)
        tabs.addTab(config_widget, "配置")
        
        # 客户端页
        client_widget = QWidget()
        client_layout = QVBoxLayout(client_widget)
        tabs.addTab(client_widget, "客户端")
        
        # 加载配置
        self.load_config()
        
        # 创建配置界面
        self.create_config_ui(config_layout)
        
        # 创建客户端界面
        self.create_client_ui(client_layout)
        
        # 创建状态栏
        self.statusBar().showMessage('就绪')
        
        # 添加解析器字典
        self.parsers = {
            'COM5': self.parse_com5_frame,
            'default': self.parse_default_frame
        }
        
    def load_config(self):
        """加载配置文件"""
        if os.path.exists('config.yaml'):
            with open('config.yaml', 'r', encoding='utf-8') as file:
                self.config = yaml.safe_load(file)
            
            # 确保serial_ports配置存在
            if 'serial_ports' not in self.config:
                self.config['serial_ports'] = [
                    {'name': 'COM1', 'baudrate': 9600},
                    {'name': 'COM2', 'baudrate': 9600},
                    {'name': 'COM3', 'baudrate': 9600}
                ]
        else:
            self.config = {
                'serial_ports': [
                    {'name': 'COM1', 'baudrate': 9600},
                    {'name': 'COM2', 'baudrate': 9600},
                    {'name': 'COM3', 'baudrate': 9600}
                ]
                # ... 其他默认配置 ...
            }
            
    def save_config(self):
        """保存配置文件"""
        # 串口时间配置
        self.config['serial']['send_time'] = float(self.serial_send_time.text())
        self.config['serial']['receive_time'] = float(self.serial_receive_time.text())
        self.config['serial']['send_error_time'] = float(self.serial_send_error_time.text())
        self.config['serial']['receive_error_time'] = float(self.serial_receive_error_time.text())
        
        # TCP服务器配置
        self.config['tcp_server']['buffer_size'] = int(self.buffer_size.text())
        self.config['tcp_server']['host'] = self.tcp_host.text()
        self.config['tcp_server']['port'] = int(self.tcp_port.text())
        self.config['tcp_server']['max_connections'] = int(self.max_connections.text())
        
        # 保存到文件
        with open('config.yaml', 'w', encoding='utf-8') as file:
            yaml.dump(self.config, file, allow_unicode=True)
            
        self.statusBar().showMessage('配置已保存', 3000)
        
    def create_config_ui(self, layout):
        """创建配置界面"""
        
        # 串口配置组
        serial_group = QGroupBox("串口配置")
        serial_layout = QVBoxLayout()
        
        # 删除 default_serial_config 相关控件，只保留时间配置
        self.serial_send_time = QLineEdit(str(self.config['serial']['send_time']))
        self.serial_receive_time = QLineEdit(str(self.config['serial']['receive_time']))
        self.serial_send_error_time = QLineEdit(str(self.config['serial']['send_error_time']))
        self.serial_receive_error_time = QLineEdit(str(self.config['serial']['receive_error_time']))
        
        serial_layout.addWidget(QLabel("发送间隔时间:"))
        serial_layout.addWidget(self.serial_send_time)
        serial_layout.addWidget(QLabel("接收间隔时间:"))
        serial_layout.addWidget(self.serial_receive_time)
        serial_layout.addWidget(QLabel("发送错误间隔时间:"))
        serial_layout.addWidget(self.serial_send_error_time)
        serial_layout.addWidget(QLabel("接收错误间隔时间:"))
        serial_layout.addWidget(self.serial_receive_error_time)

        serial_group.setLayout(serial_layout)
        layout.addWidget(serial_group)
        
        # TCP服务器配置组
        tcp_group = QGroupBox("TCP服务器配置")
        tcp_layout = QVBoxLayout()
        
        self.buffer_size = QLineEdit(str(self.config['tcp_server']['buffer_size']))
        self.tcp_host = QLineEdit(self.config['tcp_server']['host'])
        self.tcp_port = QLineEdit(str(self.config['tcp_server']['port']))
        self.max_connections = QLineEdit(str(self.config['tcp_server']['max_connections']))
        
        tcp_layout.addWidget(QLabel("TCP地址:"))
        tcp_layout.addWidget(self.tcp_host)
        tcp_layout.addWidget(QLabel("TCP端口:"))
        tcp_layout.addWidget(self.tcp_port)
        tcp_layout.addWidget(QLabel("最大连接数:"))
        tcp_layout.addWidget(self.max_connections)
        tcp_layout.addWidget(QLabel("缓冲区大小:"))
        tcp_layout.addWidget(self.buffer_size)
        

        tcp_group.setLayout(tcp_layout)
        layout.addWidget(tcp_group)
        
        # 保存按钮
        save_btn = QPushButton("保存配置")
        save_btn.clicked.connect(self.save_config)
        layout.addWidget(save_btn)
        
    def create_client_ui(self, layout):
        """创建客户端界面"""
        # 连接控制组
        connect_group = QGroupBox("连接控制")
        connect_layout = QHBoxLayout()
        
        self.connect_btn = QPushButton("连接服务器")
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.connection_status = QLabel("未连接")
        self.connection_status.setStyleSheet("color: red")
        
        connect_layout.addWidget(self.connect_btn)
        connect_layout.addWidget(self.connection_status)
        
        connect_group.setLayout(connect_layout)
        layout.addWidget(connect_group)

        # 操作类型选择
        action_group = QGroupBox("操作类型")
        action_layout = QHBoxLayout()
        
        self.action_combo = QComboBox()
        self.action_combo.addItems(['send', 'receive', 'queue_size', 'status', 'clear_queue'])
        self.action_combo.currentTextChanged.connect(self.on_action_changed)
        
        action_layout.addWidget(QLabel("操作:"))
        action_layout.addWidget(self.action_combo)
        
        action_group.setLayout(action_layout)
        layout.addWidget(action_group)
        
        # 在操作类型选择后添加串口选择
        port_group = QGroupBox("串口选择")
        port_layout = QHBoxLayout()
        
        self.port_combo = QComboBox()
        # 从配置文件中获取所有串口
        serial_ports = self.config.get('serial_ports', [])
        port_names = [port['name'] for port in serial_ports]
        self.port_combo.addItems(port_names)
        
        port_layout.addWidget(QLabel("选择串口:"))
        port_layout.addWidget(self.port_combo)
        
        port_group.setLayout(port_layout)
        layout.addWidget(port_group)
        
        # 参数设置组
        self.param_group = QGroupBox("参数设置")
        self.param_layout = QVBoxLayout()
        
        # send参数
        self.send_params = QWidget()
        send_layout = QVBoxLayout()
        self.data_inputs = []
        labels = ["从机号", "功能码", "起始寄存器", "寄存器数量"]
        for i in range(4):
            data_input = QSpinBox()
            data_input.setRange(0, 255)
            self.data_inputs.append(data_input)
            send_layout.addWidget(QLabel(f"{labels[i]}:"))
            send_layout.addWidget(data_input)
        self.send_params.setLayout(send_layout)
        
        # receive参数
        self.receive_params = QWidget()
        receive_layout = QVBoxLayout()
        self.num_input = QSpinBox()
        self.num_input.setRange(1, 100)
        receive_layout.addWidget(QLabel("接收帧数:"))
        receive_layout.addWidget(self.num_input)
        self.receive_params.setLayout(receive_layout)
        
        self.param_layout.addWidget(self.send_params)
        self.param_layout.addWidget(self.receive_params)
        self.param_group.setLayout(self.param_layout)
        layout.addWidget(self.param_group)

        # 响应显示
        response_group = QGroupBox("响应")
        response_layout = QVBoxLayout()
        self.response_text = QTextEdit()
        self.response_text.setReadOnly(True)
        response_layout.addWidget(self.response_text)
        response_group.setLayout(response_layout)
        layout.addWidget(response_group)
        
        # 发送控制组
        send_control_group = QGroupBox("发送控制")
        send_control_layout = QHBoxLayout()
        
        # 发送按钮
        send_btn = QPushButton("发送请求")
        send_btn.clicked.connect(self.send_client_request)
        
        # 连续发送控制
        self.continuous_send_btn = QPushButton("开始连续发送")
        self.continuous_send_btn.clicked.connect(self.toggle_continuous_send)
        
        # 发送间隔设置
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(100, 10000)  # 100ms到10000ms
        self.interval_spinbox.setValue(1000)  # 默认1000ms
        self.interval_spinbox.setSuffix("ms")
        
        send_control_layout.addWidget(send_btn)
        send_control_layout.addWidget(self.continuous_send_btn)
        send_control_layout.addWidget(QLabel("发送间隔:"))
        send_control_layout.addWidget(self.interval_spinbox)
        
        send_control_group.setLayout(send_control_layout)
        layout.addWidget(send_control_group)
        
        # 初始化按钮状态
        self.update_ui_state()
        
        # 初始化显示
        self.on_action_changed('send')
    
    def toggle_connection(self):
        """切换连接状态"""
        try:
            if not self.is_connected:
                # 尝试连接服务器
                try:
                    # 如果socket已关闭，创建新的socket
                    if self.client_socket._closed:
                        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        self.client_socket.settimeout(5.0)
                        
                    self.client_socket.connect((self.config['tcp_server']['host'], 
                                            self.config['tcp_server']['port']))
                    self.is_connected = True
                    self.connection_status.setText("已连接")
                    self.connection_status.setStyleSheet("color: green")
                    self.connect_btn.setText("断开连接")
                except socket.timeout:
                    self.response_text.setText("连接超时")
                except ConnectionRefusedError:
                    self.response_text.setText("连接被拒绝，服务器可能未启动")
                except Exception as e:
                    self.response_text.setText(f"连接错误: {str(e)}")
            else:
                self.disconnect_from_server()
                
            self.update_ui_state()
            
        except Exception as e:
            self.response_text.setText(f"连接错误: {str(e)}")
            
    def toggle_continuous_send(self):
        """切换连续发送状态"""
        if not self.is_continuous_sending:
            self.is_continuous_sending = True
            self.continuous_send_btn.setText("停止连续发送")
            self.interval_spinbox.setEnabled(False)
            self.send_timer.start(self.interval_spinbox.value())
        else:
            self.is_continuous_sending = False
            self.continuous_send_btn.setText("开始连续发送")
            self.interval_spinbox.setEnabled(True)
            self.send_timer.stop()
            
    def update_ui_state(self):
        """更新UI状态"""
        connected = self.is_connected
        self.continuous_send_btn.setEnabled(connected)
        self.interval_spinbox.setEnabled(connected and not self.is_continuous_sending)

    def on_action_changed(self, action):
        """处理操作类型改变"""
        self.send_params.setVisible(action == 'send')
        self.receive_params.setVisible(action == 'receive')
        
    def parse_com5_frame(self, frame_hex):
        """解析COM5的Modbus帧"""
        try:
            # 将十六进制字符串转换为字节
            frame = bytes.fromhex(frame_hex)
            
            # CRC校验
            crc = self.calculate_crc(frame[:-2])
            if crc != frame[-2:]:
                return f"CRC校验失败: {frame_hex}"
            
            # 解析响应
            if frame[1] == 0x03:
                slave_address = frame[0]
                main_open = (frame[3] << 8) | frame[4] == 0x0001
                light_open = (frame[5] << 8) | frame[6] == 0x0001
                fan_rate = (frame[7] << 8) | frame[8]
                temperature = (frame[9] << 8) | frame[10]
                
                return {
                    "从机号": slave_address,
                    "总控开关": main_open,
                    "灯光开关": light_open,
                    "风扇转速": fan_rate,
                    "温度": temperature
                }
            else:
                return f"不支持的功能码: {frame[1]}"
                
        except Exception as e:
            return f"解析错误: {str(e)}"
            
    def parse_default_frame(self, frame_hex):
        """默认的Modbus帧解析模板"""
        try:
            frame = bytes.fromhex(frame_hex)
            
            # CRC校验
            crc = self.calculate_crc(frame[:-2])
            if crc != frame[-2:]:
                return f"CRC校验失败: {frame_hex}"
            
            # 基本信息解析
            slave_address = frame[0]
            function_code = frame[1]
            data_length = frame[2]
            data = frame[3:-2]
            
            return {
                "从机号": slave_address,
                "功能码": function_code,
                "数据长度": data_length,
                "数据": data.hex(),
                "CRC": frame[-2:].hex()
            }
            
        except Exception as e:
            return f"解析错误: {str(e)}"
            
    def calculate_crc(self, data):
        """CRC计算函数"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc = crc >> 1
        return crc.to_bytes(2, byteorder='little')

    def _build_request(self, action, selected_port):
        """构造请求数据"""
        request = {
            "action": action,
            "port": selected_port
        }
        
        # 根据不同action添加特定参数
        if action == 'receive':
            request["num"] = int(self.num_input.value())
        elif action == 'send':
            request["data"] = [input.value() for input in self.data_inputs]
        
        return request

    def _send_and_receive(self, request):
        """发送请求并接收响应"""
        try:
            self.client_socket.send(json.dumps(request).encode('utf-8'))
            response = self.client_socket.recv(4096)
            return json.loads(response.decode('utf-8'))
        except socket.timeout:
            self.response_text.setText("错误: 连接超时")
            self.disconnect_from_server()
        except ConnectionResetError:
            self.response_text.setText("错误: 连接被重置")
            self.disconnect_from_server()
        except Exception as e:
            self.response_text.setText(f"错误: {str(e)}")
            self.disconnect_from_server()
        return None

    def _handle_response(self, action, response_data, port_name):
        """处理服务器响应"""
        if response_data["status"] != "success":
            self.response_text.setText(json.dumps(response_data, indent=2, ensure_ascii=False))
            return
        
        if action == 'receive':
            # 解析接收到的帧
            parser = self.parsers.get(port_name, self.parsers['default'])
            parsed_frames = [parser(frame_hex) for frame_hex in response_data.get("frames", [])]
            
            # 显示解析结果
            result = {
                "status": "success",
                "port": port_name,
                "parsed_data": parsed_frames
            }
            self.response_text.setText(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            # 其他action直接显示响应
            self.response_text.setText(json.dumps(response_data, indent=2, ensure_ascii=False))

    def send_client_request(self):
        """发送客户端请求"""
        if not self.is_connected:
            self.response_text.setText("错误: 未连接到服务器")
            return

        action = self.action_combo.currentText()
        selected_port = self.port_combo.currentText()

        try:
            # 根据不同action构造请求
            request = self._build_request(action, selected_port)
            if not request:
                return
            
            # 发送请求并获取响应
            response_data = self._send_and_receive(request)
            if not response_data:
                return
            
            # 处理响应
            self._handle_response(action, response_data, selected_port)
            
        except Exception as e:
            self.response_text.setText(f"请求错误: {str(e)}")
            self.disconnect_from_server()

    def disconnect_from_server(self):
        """断开服务器连接"""
        try:
            self.client_socket.close()
        except:
            pass
            
        # 创建新的socket以备后用
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.settimeout(5.0)
        
        self.is_connected = False
        self.connection_status.setText("未连接")
        self.connection_status.setStyleSheet("color: red")
        self.connect_btn.setText("连接服务器")
        
        # 如果正在连续发送，停止它
        if self.is_continuous_sending:
            self.toggle_continuous_send()
            
        self.update_ui_state()   

def main():
    app = QApplication(sys.argv)
    window = ConfigClientGUI()
    window.show()
    sys.exit(app.exec_())
    
if __name__ == '__main__':
    main() 