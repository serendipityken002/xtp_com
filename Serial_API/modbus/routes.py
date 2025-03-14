from flask import Blueprint

import os
import yaml

# 加载配置文件
config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
with open(config_path, 'r', encoding='utf-8') as file:
    config = yaml.safe_load(file)

modbus_bp = Blueprint('modbus', __name__)

@modbus_bp.route('/send', methods=['POST'])
def send_modbus_frame():
    pass

