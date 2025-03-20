import requests

url = "http://127.0.0.1:5000/send_data"
data = {
    "slave_adress": "1",
    "function_code": "3",
    "start_address": "2",
    "quantity": "4"
}

response = requests.post(url, json=data)

if response.status_code == 200:
    print("成功:", response.json())
else:
    print("失败:", response.status_code, response.text)