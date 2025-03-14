import axios from 'axios';

const API_URL = 'http://127.0.0.1:5000/api';

export default {
  // 串口相关API
  serialPort: {
    // 获取可用串口列表
    getAvailablePorts() {
      return axios.get(`${API_URL}/serial/ports`);
    },
    
    // 打开串口
    openPort(port, baudrate = 115200) {
      return axios.post(`${API_URL}/serial/start`, { port, baudrate });
    },
    
    // 关闭串口
    closePort(port) {
      return axios.post(`${API_URL}/serial/stop`, { port });
    },
    
    // 发送数据到串口
    sendData(port, data) {
      return axios.post(`${API_URL}/serial/send`, { port, data });
    },
    
    // 获取串口状态
    getStatus(port) {
      return axios.post(`${API_URL}/serial/status`, { port });
    }
  },
  
  // Modbus相关API
  modbus: {
    // 发送Modbus帧
    sendFrame(port, frame) {
      return axios.post(`${API_URL}/modbus/send`, { port, frame });
    },
    
    // 获取历史Modbus帧
    getFrameHistory(limit = 50, offset = 0) {
      return axios.get(`${API_URL}/modbus/history`, { 
        params: { limit, offset } 
      });
    },
    
    // 获取最新的Modbus帧响应
    getLatestResponse(frameId) {
      return axios.get(`${API_URL}/modbus/response/${frameId}`);
    },
    
    // 按照ID获取特定的Modbus帧
    getFrameById(frameId) {
      return axios.get(`${API_URL}/modbus/frame/${frameId}`);
    },
    
    // 按照时间范围获取Modbus帧
    getFramesByTimeRange(startTime, endTime) {
      return axios.get(`${API_URL}/modbus/frames/range`, {
        params: { startTime, endTime }
      });
    }
  },
  
  // 配置相关API
  config: {
    // 获取服务器配置
    getConfig() {
      return axios.get(`${API_URL}/config`);
    },
    
    // 更新服务器配置
    updateConfig(config) {
      return axios.post(`${API_URL}/config/update`, config);
    }
  }
}; 