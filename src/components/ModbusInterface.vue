<template>
  <div class="modbus-interface">
    <div class="control-panel">
      <h2>Modbus串口控制面板</h2>
      
      <div class="port-selector">
        <label for="port-select">选择串口:</label>
        <select id="port-select" v-model="selectedPort">
          <option v-for="port in availablePorts" :key="port" :value="port">{{ port }}</option>
        </select>
        
        <button 
          :class="{'open': portStatus, 'closed': !portStatus}" 
          @click="togglePort"
        >
          {{ portStatus ? '关闭' : '打开' }}当前串口
        </button>
      </div>
      
      <div class="communication-status">
        <div class="status-indicator" :class="{'active': portStatus}">
          <span>状态: {{ portStatus ? '已连接' : '未连接' }}</span>
        </div>
        <div v-if="portStatus" class="status-details">
          <span>已连接到: {{ selectedPort }}</span>
          <span>波特率: {{ baudRate }}</span>
        </div>
      </div>
    </div>
    
    <div class="content-container">
      <div class="left-panel">
        <ModbusFrameBuilder @frame-built="handleFrameBuilt" />
      </div>
      
      <div class="right-panel">
        <div class="data-display">
          <h3>通信数据</h3>
          
          <div class="tabs">
            <button 
              :class="{ active: activeTab === 'requests' }" 
              @click="activeTab = 'requests'"
            >
              请求
            </button>
            <button 
              :class="{ active: activeTab === 'responses' }" 
              @click="activeTab = 'responses'"
            >
              响应
            </button>
            <button 
              :class="{ active: activeTab === 'history' }" 
              @click="activeTab = 'history'"
            >
              历史记录
            </button>
          </div>
          
          <div class="tab-content">
            <!-- 请求标签页 -->
            <div v-if="activeTab === 'requests'" class="requests-tab">
              <div v-if="latestRequest" class="frame-details">
                <h4>最新请求</h4>
                <p><strong>时间:</strong> {{ formatTime(latestRequest.timestamp) }}</p>
                <p><strong>从站地址:</strong> {{ latestRequest.decoded.slaveAddress }}</p>
                <p><strong>功能码:</strong> {{ latestRequest.decoded.functionCode }} ({{ latestRequest.decoded.functionName }})</p>
                <p><strong>起始地址:</strong> {{ latestRequest.decoded.startAddress }}</p>
                <p><strong>原始帧:</strong> {{ latestRequest.frame }}</p>
              </div>
              <div v-else class="no-data">
                <p>无请求数据</p>
              </div>
            </div>
            
            <!-- 响应标签页 -->
            <div v-if="activeTab === 'responses'" class="responses-tab">
              <div v-if="latestResponse" class="frame-details">
                <h4>最新响应</h4>
                <p><strong>时间:</strong> {{ formatTime(latestResponse.timestamp) }}</p>
                <p><strong>状态:</strong> {{ latestResponse.valid ? '有效' : '无效' }}</p>
                <div v-if="latestResponse.valid">
                  <p><strong>从站地址:</strong> {{ latestResponse.slaveAddress }}</p>
                  <p><strong>功能码:</strong> {{ latestResponse.functionCode }}</p>
                  <div v-if="latestResponse.values">
                    <p><strong>数据值:</strong></p>
                    <ul class="value-list">
                      <li v-for="(value, index) in latestResponse.values" :key="index">
                        地址 {{ latestResponse.startAddress + index }}: {{ value }}
                      </li>
                    </ul>
                  </div>
                </div>
                <div v-else>
                  <p><strong>错误:</strong> {{ latestResponse.error }}</p>
                </div>
                <p><strong>原始帧:</strong> {{ latestResponse.frame }}</p>
              </div>
              <div v-else class="no-data">
                <p>无响应数据</p>
              </div>
            </div>
            
            <!-- 历史记录标签页 -->
            <div v-if="activeTab === 'history'" class="history-tab">
              <div class="history-filters">
                <button @click="loadHistory">刷新历史记录</button>
                <select v-model="historyLimit">
                  <option value="10">显示10条</option>
                  <option value="25">显示25条</option>
                  <option value="50">显示50条</option>
                  <option value="100">显示100条</option>
                </select>
              </div>
              
              <div class="history-list">
                <div v-for="item in frameHistory" :key="item.id" class="history-item" :class="{ 'error': item.error }">
                  <div class="history-item-header">
                    <span class="history-timestamp">{{ formatTime(item.timestamp) }}</span>
                    <span class="history-type">{{ item.type === 'request' ? '请求' : '响应' }}</span>
                  </div>
                  <div class="history-item-content">
                    <p class="history-device">设备: {{ item.slaveAddress }}</p>
                    <p class="history-frame">{{ item.frame }}</p>
                    <p v-if="item.error" class="history-error">错误: {{ item.error }}</p>
                  </div>
                </div>
                <div v-if="frameHistory.length === 0" class="no-data">
                  <p>无历史数据</p>
                </div>
              </div>
              
              <div class="history-pagination">
                <button 
                  :disabled="historyOffset === 0" 
                  @click="previousPage"
                >
                  上一页
                </button>
                <span>第 {{ Math.floor(historyOffset / historyLimit) + 1 }} 页</span>
                <button 
                  :disabled="frameHistory.length < historyLimit" 
                  @click="nextPage"
                >
                  下一页
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import ModbusFrameBuilder from './ModbusFrameBuilder.vue';
import ApiService from '../services/ApiService';
import { parseModbusResponse, hexStringToBytes, bytesToHexString } from '../utils/ModbusUtils';
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';

const availablePorts = ref([]);
const selectedPort = ref('');
const baudRate = ref(115200);
const portStatus = ref(false);
const activeTab = ref('requests');
const latestRequest = ref(null);
const latestResponse = ref(null);
const frameHistory = ref([]);
const historyLimit = ref(10);
const historyOffset = ref(0);
const pollingInterval = ref(null);

const loadPorts = async () => {
  try {
    const response = await ApiService.serialPort.getAvailablePorts();
    availablePorts.value = response.data.ports || [];
    if (availablePorts.value.length > 0 && !selectedPort.value) {
      selectedPort.value = availablePorts.value[0];
    }
  } catch (error) {
    console.error('获取串口列表失败:', error);
  }
};

const togglePort = async () => {
  if (!selectedPort.value) return;
  
  try {
    if (portStatus.value) {
      // 关闭串口
      await ApiService.serialPort.closePort(selectedPort.value);
      portStatus.value = false;
      
      // 停止轮询
      if (pollingInterval.value) {
        clearInterval(pollingInterval.value);
        pollingInterval.value = null;
      }
    } else {
      // 打开串口
      await ApiService.serialPort.openPort(selectedPort.value, baudRate.value);
      portStatus.value = true;
      
      // 开始轮询新响应
      startPolling();
    }
  } catch (error) {
    console.error('串口操作失败:', error);
    alert(`串口操作失败: ${error.message}`);
  }
};

const checkPortStatus = async () => {
  if (!selectedPort.value) return;
  
  try {
    const response = await ApiService.serialPort.getStatus(selectedPort.value);
    portStatus.value = response.data.isOpen;
  } catch (error) {
    console.error('获取串口状态失败:', error);
  }
};

const handleFrameBuilt = async (frameData) => {
  if (!portStatus.value) {
    alert('请先打开串口');
    return;
  }
  
  try {
    // 保存请求
    latestRequest.value = {
      timestamp: new Date(),
      frame: frameData.hex,
      bytes: frameData.bytes,
      decoded: frameData.decoded
    };
    
    // 发送到服务器
    const response = await ApiService.modbus.sendFrame(selectedPort.value, frameData.hex);
    
    if (response.data && response.data.status === 'success') {
      // 如果成功，自动切换到响应标签页
      activeTab.value = 'responses';
      
      // 解析响应
      if (response.data.response) {
        const responseBytes = hexStringToBytes(response.data.response);
        const parsedResponse = parseModbusResponse(responseBytes, frameData.bytes);
        
        latestResponse.value = {
          ...parsedResponse,
          timestamp: new Date(),
          frame: response.data.response
        };
      }
    }
  } catch (error) {
    console.error('发送Modbus帧失败:', error);
    alert(`发送Modbus帧失败: ${error.message}`);
  }
};

const startPolling = () => {
  // 每秒轮询一次历史记录
  pollingInterval.value = setInterval(() => {
    if (activeTab.value === 'history') {
      loadHistory();
    }
  }, 1000);
};

const loadHistory = async () => {
  try {
    const response = await ApiService.modbus.getFrameHistory(
      historyLimit.value, 
      historyOffset.value
    );
    
    if (response.data && response.data.frames) {
      frameHistory.value = response.data.frames.map(frame => ({
        ...frame,
        timestamp: new Date(frame.timestamp)
      }));
    }
  } catch (error) {
    console.error('获取历史记录失败:', error);
  }
};

const previousPage = () => {
  if (historyOffset.value >= historyLimit.value) {
    historyOffset.value -= historyLimit.value;
    loadHistory();
  }
};

const nextPage = () => {
  if (frameHistory.value.length === parseInt(historyLimit.value)) {
    historyOffset.value += parseInt(historyLimit.value);
    loadHistory();
  }
};

const formatTime = (timestamp) => {
  if (!timestamp) return '';
  
  const date = new Date(timestamp);
  return date.toLocaleString('zh-CN', { 
    year: 'numeric', 
    month: '2-digit', 
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  });
};

onMounted(() => {
  loadPorts();
  checkPortStatus();
  loadHistory();
});

onBeforeUnmount(() => {
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value);
  }
});

watch(historyLimit, () => {
  historyOffset.value = 0; // 重置偏移量
  loadHistory();
});
</script>

<style scoped>
.modbus-interface {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.control-panel {
  background-color: #f5f5f5;
  border-radius: 8px;
  padding: 15px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.port-selector {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 15px;
}

select, button {
  padding: 8px 12px;
  border-radius: 4px;
  border: 1px solid #ccc;
}

button {
  cursor: pointer;
  font-weight: bold;
}

button.open {
  background-color: green;
  color: white;
}

button.closed {
  background-color: red;
  color: white;
}

.communication-status {
  display: flex;
  align-items: center;
  gap: 20px;
}

.status-indicator {
  padding: 8px 12px;
  border-radius: 4px;
  background-color: #ddd;
  display: inline-block;
}

.status-indicator.active {
  background-color: #4CAF50;
  color: white;
}

.content-container {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
}

.left-panel {
  flex: 1;
  min-width: 400px;
}

.right-panel {
  flex: 1;
  min-width: 400px;
}

.data-display {
  background-color: #f9f9f9;
  border-radius: 8px;
  padding: 15px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.tabs {
  display: flex;
  gap: 5px;
  margin-bottom: 15px;
  border-bottom: 1px solid #ddd;
  padding-bottom: 10px;
}

.tabs button {
  background-color: #f1f1f1;
  border: none;
  padding: 8px 15px;
  border-radius: 4px 4px 0 0;
}

.tabs button.active {
  background-color: #2196F3;
  color: white;
}

.tab-content {
  background-color: white;
  border-radius: 4px;
  padding: 15px;
  min-height: 300px;
}

.frame-details {
  margin-bottom: 15px;
}

.value-list {
  max-height: 150px;
  overflow-y: auto;
  border: 1px solid #eee;
  padding: 10px;
  border-radius: 4px;
  background-color: #f9f9f9;
}

.no-data {
  text-align: center;
  padding: 30px;
  color: #777;
  font-style: italic;
}

.history-filters {
  display: flex;
  justify-content: space-between;
  margin-bottom: 15px;
}

.history-list {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #eee;
  border-radius: 4px;
}

.history-item {
  padding: 10px;
  border-bottom: 1px solid #eee;
}

.history-item:last-child {
  border-bottom: none;
}

.history-item.error {
  background-color: #ffebee;
}

.history-item-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 5px;
  font-size: 0.9em;
}

.history-timestamp {
  color: #666;
}

.history-type {
  font-weight: bold;
}

.history-item-content {
  font-family: monospace;
}

.history-error {
  color: red;
  font-weight: bold;
}

.history-pagination {
  display: flex;
  justify-content: center;
  gap: 15px;
  align-items: center;
  margin-top: 15px;
  padding-top: 10px;
  border-top: 1px solid #eee;
}

h2, h3, h4 {
  color: #333;
  margin-top: 0;
}
</style> 