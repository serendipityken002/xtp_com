from flask import Flask, request, jsonify
from flask_cors import CORS
from dataprocess import send_data, process_data_thread
from serial_serve import start_serial_process

app = Flask(__name__)
CORS(app)

import logging
from logging.config import dictConfig
from datetime import datetime
import os

def setup_logging():
    log_dir = 'logs'
    error_log_dir = os.path.join(log_dir, 'wrong_log')
    print_log_dir = os.path.join(log_dir, 'print_log')

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    if not os.path.exists(error_log_dir):
        os.makedirs(error_log_dir)
    if not os.path.exists(print_log_dir):
        os.makedirs(print_log_dir)

    today_str = datetime.now().strftime('%Y-%m-%d')
    error_today_dir = os.path.join(error_log_dir, today_str)
    print_today_dir = os.path.join(print_log_dir, today_str)
    if not os.path.exists(error_today_dir):
        os.makedirs(error_today_dir)
    if not os.path.exists(print_today_dir):
        os.makedirs(print_today_dir)

    time_now = datetime.now().strftime('%H-%M-%S')
    error_log_file = os.path.join(error_today_dir, f'{time_now}.txt')
    print_log_file = os.path.join(print_today_dir, f'debug_{today_str}.log')

    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'INFO',
                'formatter': 'standard',
                'stream': 'ext://sys.stdout',
            },
            'error_file': {
                'class': 'logging.FileHandler',
                'level': 'ERROR',
                'formatter': 'standard',
                'filename': error_log_file,
                'mode': 'a',
            },
            'print_file': {
                'class': 'logging.FileHandler',
                'level': 'DEBUG',
                'formatter': 'standard',
                'filename': print_log_file,
                'mode': 'a',
            },
        },
        'loggers': {
            '': {  # root logger
                'handlers': ['console', 'error_file', 'print_file'],
                'level': 'DEBUG',
                'propagate': True
            },
            'SerialServer': {
                'handlers': ['console', 'error_file', 'print_file'],
                'level': 'DEBUG',
                'propagate': False
            },
        }
    }

    dictConfig(LOGGING_CONFIG)

@app.route('/send_data', methods=['POST'])
def send():
    """发送数据"""
    data = request.json
    slave_address = data['slave_address']
    function_code = data['function_code']
    start_address = data['start_address']
    quantity = data['quantity']
    send_data(slave_address, function_code, start_address, quantity)
    return jsonify({'message': '数据发送成功'})

if __name__ == '__main__':
    # 在主程序中调用setup_logging()进行配置
    setup_logging()
    logger = logging.getLogger(__name__)
    start_serial_process()
    process_data_thread()
    app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)
