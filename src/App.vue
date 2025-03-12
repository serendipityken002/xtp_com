<script setup>
import { reactive, onMounted } from 'vue'
import axios from 'axios'

const ports = [
  ['COM10', 'COM11'],
  ['COM12', 'COM13'],
  ['COM14', 'COM15']
];

const sendData = reactive({});
const receiveData = reactive({});
const portStatus = reactive({});

ports.forEach(portPair => {
  portPair.forEach(port => {
    sendData[port] = '';
    receiveData[port] = '';
    portStatus[port] = false;
  });
});

const openPort = async (port) => {
  try {
    const response = await axios.post('http://127.0.0.1:5000/api/serial/start', { port });
    console.log(`串口 ${port} 已打开:`, response.data);
    getStatus(port);
  } catch (error) {
    alert(`无法打开串口 ${port}: ${error}`);
  }
};

const closePort = async (port) => {
  try {
    const response = await axios.post('http://127.0.0.1:5000/api/serial/stop', { port });
    console.log(`串口 ${port} 已关闭:`, response.data);
    getStatus(port);
  } catch (error) {
    alert(`无法关闭串口 ${port}: ${error}`);
  }
};

const sendDataToPort = async (port) => {
  try {
    const response = await axios.post('http://127.0.0.1:5000/api/serial/send', { port, data: sendData[port] });
    console.log(`数据已发送到串口 ${port}:`, response.data);
  } catch (error) {
    alert(`无法发送数据到串口 ${port}: ${error}`);
  }
};

const getStatus = async (port) => {
  try {
    const response = await axios.post('http://127.0.0.1:5000/api/serial/status', { port });
    portStatus[port] = response.data.isOpen;
    receiveData[port] = response.data.data;
  } catch (error) {
    console.error('数据接收失败', error);
  }
};

onMounted(() => {
  ports.forEach(portPair => {
    portPair.forEach(port => {
      getStatus(port); // 获取每个端口的状态
    });
  });
});

</script>

<template>
  <div class="container">
    <div v-for="(port, index) in ports" :key="index" class="port-pair">
      <h3>串口 {{ port[0] }}</h3>
      <button :class="{'open': portStatus[port[0]], 'closed': !portStatus[port[0]]}" @click="portStatus[port[0]] ? closePort(port[0]) : openPort(port[0])">
        {{ portStatus[port[0]] ? '关闭' : '打开' }}当前串口
      </button>
      <div class="input-group">
        <label for="send-{{ port[0] }}">数据发送</label>
        <textarea id="send-{{ port[0] }}" v-model="sendData[port[0]]"></textarea>
        <button @click="sendDataToPort(port[0])">发送</button>

        <label for="receive-{{ port[0] }}">记录</label>
        <textarea readonly id="receive-{{ port[0] }}" v-model="receiveData[port[0]]"></textarea>
      </div>
      
      <h3>串口 {{ port[1] }}</h3>
      <button :class="{'open': portStatus[port[1]], 'closed': !portStatus[port[1]]}" @click="portStatus[port[1]] ? closePort(port[1]) : openPort(port[1])">
        {{ portStatus[port[1]] ? '关闭' : '打开' }}当前串口
      </button>
      <div class="input-group">
        <label for="send-{{ port[1] }}">数据发送</label>
        <textarea id="send-{{ port[1] }}" v-model="sendData[port[1]]"></textarea>
        <button @click="sendDataToPort(port[1])">发送</button>

        <label for="receive-{{ port[1] }}">记录</label>
        <textarea readonly id="receive-{{ port[1] }}" v-model="receiveData[port[1]]"></textarea>
      </div>
    </div>
  </div>
</template>

<style scoped>
.container {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  padding: 20px;
}

.port-pair {
  border: 1px solid #ccc;
  border-radius: 10px;
  padding: 20px;
  width: calc(33.333% - 40px);
  box-sizing: border-box;
}

.input-group {
  margin-bottom: 20px;
}

.input-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: bold;
}

.input-group textarea {
  width: 100%;
  height: 100px;
  margin-top: 8px;
  padding: 10px;
  box-sizing: border-box;
  border: 1px solid #ccc;
  border-radius: 5px;
}

h3 {
  text-align: center;
  color: #333;
}

button {
  padding: 10px 20px;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  margin-bottom: 20px;
}

button.open {
  background-color: green;
  color: white;
}

button.closed {
  background-color: red;
  color: white;
}
</style>