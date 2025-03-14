/**
 * Modbus工具类，用于处理和解析Modbus数据帧
 */

// Modbus功能码及其描述
export const FUNCTION_CODES = {
  1: '读取线圈状态',
  2: '读取输入状态',
  3: '读取保持寄存器',
  4: '读取输入寄存器',
  5: '写入单个线圈',
  6: '写入单个寄存器',
  15: '写入多个线圈',
  16: '写入多个寄存器'
};

// Modbus错误码及其描述
export const ERROR_CODES = {
  0x81: '非法功能',
  0x82: '非法数据地址',
  0x83: '非法数据值',
  0x84: '从站设备故障',
  0x85: '确认',
  0x86: '从站设备忙',
  0x87: '存储奇偶性差错',
  0x88: '不可用网关路径',
  0x8A: '网关目标设备响应失败',
  0x8B: '网关目标设备响应超时'
};

/**
 * 计算Modbus CRC-16校验码
 * @param {Array<number>} data 要计算CRC的数据字节数组
 * @returns {number} 16位CRC值
 */
export function calculateCRC16(data) {
  let crc = 0xFFFF;
  
  for (let i = 0; i < data.length; i++) {
    crc ^= data[i];
    
    for (let j = 0; j < 8; j++) {
      if ((crc & 0x0001) !== 0) {
        crc >>= 1;
        crc ^= 0xA001;
      } else {
        crc >>= 1;
      }
    }
  }
  
  return crc;
}

/**
 * 验证Modbus帧的CRC
 * @param {Array<number>} frame 完整的Modbus帧（包含CRC）
 * @returns {boolean} CRC是否有效
 */
export function validateCRC(frame) {
  if (frame.length < 3) return false;
  
  const dataBytes = frame.slice(0, -2);
  const receivedCRC = (frame[frame.length - 1] << 8) | frame[frame.length - 2];
  const calculatedCRC = calculateCRC16(dataBytes);
  
  return receivedCRC === calculatedCRC;
}

/**
 * 解析十六进制字符串为字节数组
 * @param {string} hexString 十六进制字符串
 * @returns {Array<number>} 字节数组
 */
export function hexStringToBytes(hexString) {
  const cleanHex = hexString.replace(/\s/g, '');
  const bytes = [];
  
  for (let i = 0; i < cleanHex.length; i += 2) {
    bytes.push(parseInt(cleanHex.substr(i, 2), 16));
  }
  
  return bytes;
}

/**
 * 字节数组转为十六进制字符串
 * @param {Array<number>} bytes 字节数组
 * @returns {string} 十六进制字符串
 */
export function bytesToHexString(bytes) {
  return bytes.map(byte => byte.toString(16).padStart(2, '0')).join('');
}

/**
 * 解析Modbus响应
 * @param {Array<number>} responseBytes 响应字节数组
 * @param {Array<number>} requestBytes 请求字节数组
 * @returns {Object} 解析后的响应对象
 */
export function parseModbusResponse(responseBytes, requestBytes) {
  if (!responseBytes || responseBytes.length < 5) {
    return { valid: false, error: '响应帧太短' };
  }
  
  if (!validateCRC(responseBytes)) {
    return { valid: false, error: 'CRC校验失败' };
  }
  
  const slaveAddress = responseBytes[0];
  const functionCode = responseBytes[1];
  const isError = (functionCode & 0x80) !== 0;
  
  let result = {
    valid: true,
    slaveAddress,
    functionCode,
    isError
  };
  
  if (isError) {
    const errorCode = functionCode;
    const errorReason = ERROR_CODES[errorCode] || '未知错误';
    result.error = `错误码 ${errorCode.toString(16)}: ${errorReason}`;
    return result;
  }
  
  // 解析响应数据，根据功能码
  if (requestBytes && requestBytes.length > 1) {
    const requestFunctionCode = requestBytes[1];
    result.requestedFunction = requestFunctionCode;
    
    switch (requestFunctionCode) {
      case 1: // 读取线圈状态
      case 2: // 读取输入状态
        result = parseReadCoilsResponse(responseBytes, result);
        break;
      case 3: // 读取保持寄存器
      case 4: // 读取输入寄存器
        result = parseReadRegistersResponse(responseBytes, result);
        break;
      case 5: // 写入单个线圈
        result = parseSingleWriteResponse(responseBytes, result);
        break;
      case 6: // 写入单个寄存器
        result = parseSingleWriteResponse(responseBytes, result);
        break;
      case 15: // 写入多个线圈
      case 16: // 写入多个寄存器
        result = parseMultipleWriteResponse(responseBytes, result);
        break;
      default:
        result.unknownFunction = true;
    }
  }
  
  return result;
}

/**
 * 解析读取线圈或输入状态的响应
 */
function parseReadCoilsResponse(bytes, result) {
  const byteCount = bytes[2];
  const dataBytes = bytes.slice(3, 3 + byteCount);
  
  result.byteCount = byteCount;
  result.values = [];
  
  for (let i = 0; i < byteCount; i++) {
    const byte = dataBytes[i];
    for (let bit = 0; bit < 8; bit++) {
      if (result.values.length < result.byteCount * 8) {
        result.values.push((byte >> bit) & 1);
      }
    }
  }
  
  return result;
}

/**
 * 解析读取寄存器的响应
 */
function parseReadRegistersResponse(bytes, result) {
  const byteCount = bytes[2];
  const registerCount = byteCount / 2;
  
  result.byteCount = byteCount;
  result.values = [];
  
  for (let i = 0; i < registerCount; i++) {
    const highByte = bytes[3 + i * 2];
    const lowByte = bytes[4 + i * 2];
    result.values.push((highByte << 8) | lowByte);
  }
  
  return result;
}

/**
 * 解析单个写入的响应
 */
function parseSingleWriteResponse(bytes, result) {
  result.address = (bytes[2] << 8) | bytes[3];
  result.value = (bytes[4] << 8) | bytes[5];
  return result;
}

/**
 * 解析多个写入的响应
 */
function parseMultipleWriteResponse(bytes, result) {
  result.startAddress = (bytes[2] << 8) | bytes[3];
  result.quantity = (bytes[4] << 8) | bytes[5];
  return result;
}

/**
 * Modbus帧分割器
 * 将连续的Modbus数据流分隔为单独的Modbus帧
 */
export class ModbusFrameSplitter {
  constructor() {
    this.buffer = [];
    this.minFrameLength = 4; // 从站地址(1) + 功能码(1) + CRC(2)
  }
  
  /**
   * 添加数据到缓冲区并尝试提取完整帧
   * @param {Array<number>} newData 新收到的字节数组
   * @returns {Array<Array<number>>} 提取的完整帧数组
   */
  addData(newData) {
    this.buffer = [...this.buffer, ...newData];
    return this.extractFrames();
  }
  
  /**
   * 从缓冲区中提取完整的Modbus帧
   * @returns {Array<Array<number>>} 提取的完整帧数组
   */
  extractFrames() {
    const frames = [];
    
    while (this.buffer.length >= this.minFrameLength) {
      // 尝试找到一个有效帧
      let frameEnd = -1;
      
      // RTU模式下，我们通过CRC校验来寻找帧结束位置
      for (let i = this.minFrameLength; i <= this.buffer.length; i++) {
        const potentialFrame = this.buffer.slice(0, i);
        if (validateCRC(potentialFrame)) {
          frameEnd = i;
          break;
        }
      }
      
      if (frameEnd > 0) {
        // 提取找到的帧
        const frame = this.buffer.slice(0, frameEnd);
        frames.push(frame);
        
        // 从缓冲区移除已处理的数据
        this.buffer = this.buffer.slice(frameEnd);
      } else {
        // 没有找到完整帧，保留最后3个字节（可能是下一帧的开始部分）
        if (this.buffer.length > 3) {
          this.buffer = this.buffer.slice(-3);
        }
        break;
      }
    }
    
    return frames;
  }
  
  /**
   * 清除缓冲区
   */
  clear() {
    this.buffer = [];
  }
} 