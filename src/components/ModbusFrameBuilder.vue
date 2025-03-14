<template>
  <div class="modbus-builder">
    <h3>Modbus帧构建器</h3>
    
    <div class="form-group">
      <label for="slave-address">从站地址:</label>
      <input type="number" id="slave-address" v-model.number="slaveAddress" min="1" max="247" />
    </div>

    <div class="form-group">
      <label for="function-code">功能码:</label>
      <select id="function-code" v-model.number="functionCode">
        <option v-for="(desc, code) in functionCodes" :key="code" :value="Number(code)">
          {{ code }} - {{ desc }}
        </option>
      </select>
    </div>

    <div class="form-group">
      <label for="start-address">起始地址:</label>
      <input type="number" id="start-address" v-model.number="startAddress" min="0" max="65535" />
    </div>

    <div class="form-group" v-if="needsQuantity">
      <label for="quantity">数量:</label>
      <input type="number" id="quantity" v-model.number="quantity" min="1" max="125" />
    </div>

    <div class="form-group" v-if="needsValues">
      <label>值:</label>
      <div v-for="(value, index) in values" :key="index" class="value-row">
        <input type="number" v-model.number="values[index]" min="0" max="65535" />
        <button @click="removeValue(index)" class="remove-btn">删除</button>
      </div>
      <button @click="addValue" class="add-btn">添加值</button>
    </div>

    <div class="preview">
      <h4>帧预览</h4>
      <div class="frame-hex">
        <span v-for="(byte, index) in frameBytes" :key="index" class="byte">
          {{ byte.toString(16).padStart(2, '0').toUpperCase() }}
        </span>
      </div>
    </div>

    <div class="buttons">
      <button @click="buildAndSend" class="send-btn">构建并发送</button>
      <button @click="reset" class="reset-btn">重置</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';

const emit = defineEmits(['frame-built']);

const slaveAddress = ref(1);
const functionCode = ref(3);
const startAddress = ref(0);
const quantity = ref(1);
const values = ref([0]);
const functionCodes = ref({
  1: '读取线圈状态',
  2: '读取输入状态', 
  3: '读取保持寄存器',
  4: '读取输入寄存器',
  5: '写入单个线圈',
  6: '写入单个寄存器',
  15: '写入多个线圈',
  16: '写入多个寄存器'
});
const sentFrames = ref([]);

const needsQuantity = computed(() => {
  // 需要数量参数的功能码
  return [1, 2, 3, 4, 15, 16].includes(functionCode.value);
});

const needsValues = computed(() => {
  // 需要值参数的功能码
  return [5, 6, 15, 16].includes(functionCode.value);
});

const frameBytes = computed(() => {
  const frame = [];
  
  // 从站地址
  frame.push(slaveAddress.value);
  
  // 功能码
  frame.push(functionCode.value);
  
  // 起始地址 (高字节在前)
  frame.push((startAddress.value >> 8) & 0xFF);
  frame.push(startAddress.value & 0xFF);
  
  // 根据功能码添加不同的数据
  if ([1, 2, 3, 4].includes(functionCode.value)) {
    // 读操作: 添加数量 (高字节在前)
    frame.push((quantity.value >> 8) & 0xFF);
    frame.push(quantity.value & 0xFF);
  } else if ([5, 6].includes(functionCode.value)) {
    // 单个写操作: 写入值 (高字节在前)
    const value = values.value[0] || 0;
    frame.push((value >> 8) & 0xFF);
    frame.push(value & 0xFF);
  } else if ([15, 16].includes(functionCode.value)) {
    // 多个写操作
    // 添加数量 (高字节在前)
    frame.push((quantity.value >> 8) & 0xFF);
    frame.push(quantity.value & 0xFF);
    
    if (functionCode.value === 15) {
      // 对于多个线圈，需要计算字节数
      const byteCount = Math.ceil(values.value.length / 8);
      frame.push(byteCount);
      
      // 打包比特位
      let currentByte = 0;
      let bitPosition = 0;
      
      for (let i = 0; i < values.value.length; i++) {
        if (values.value[i]) {
          currentByte |= (1 << bitPosition);
        }
        
        bitPosition++;
        if (bitPosition === 8 || i === values.value.length - 1) {
          frame.push(currentByte);
          currentByte = 0;
          bitPosition = 0;
        }
      }
    } else if (functionCode.value === 16) {
      // 对于多个寄存器
      const byteCount = values.value.length * 2;
      frame.push(byteCount);
      
      // 添加所有值
      for (const value of values.value) {
        frame.push((value >> 8) & 0xFF);
        frame.push(value & 0xFF);
      }
    }
  }
  
  // 计算CRC (简化版本)
  const crc = calculateCRC(frame);
  frame.push(crc & 0xFF);
  frame.push((crc >> 8) & 0xFF);
  
  return frame;
});

const addValue = () => {
  values.value.push(0);
  if (values.value.length > quantity.value && [15, 16].includes(functionCode.value)) {
    quantity.value = values.value.length;
  }
};

const removeValue = (index) => {
  if (values.value.length > 1) {
    values.value.splice(index, 1);
    if (quantity.value > values.value.length && [15, 16].includes(functionCode.value)) {
      quantity.value = values.value.length;
    }
  }
};

const calculateCRC = (data) => {
  // 简化的Modbus CRC-16计算
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
};

const decodeFrame = (bytes) => {
  // 解码帧内容
  const functionName = functionCodes.value[bytes[1]] || '未知功能';
  return {
    slaveAddress: bytes[0],
    functionCode: bytes[1],
    functionName,
    startAddress: (bytes[2] << 8) | bytes[3],
    // 其他解码信息取决于功能码
  };
};

const buildAndSend = () => {
  // 将帧转换为十六进制字符串
  const hexString = frameBytes.value
    .map(byte => byte.toString(16).padStart(2, '0'))
    .join('');
  
  // 保存到发送历史
  sentFrames.value.push({
    timestamp: new Date(),
    frame: hexString,
    decoded: decodeFrame(frameBytes.value)
  });
  
  // 发送事件，通知父组件
  emit('frame-built', {
    hex: hexString,
    bytes: [...frameBytes.value],
    decoded: decodeFrame(frameBytes.value)
  });
};

const reset = () => {
  slaveAddress.value = 1;
  functionCode.value = 3;
  startAddress.value = 0;
  quantity.value = 1;
  values.value = [0];
};
</script>

<style scoped>
.modbus-builder {
  padding: 20px;
  border: 1px solid #ddd;
  border-radius: 8px;
  margin-bottom: 20px;
  background-color: #f9f9f9;
}

.form-group {
  margin-bottom: 15px;
}

label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}

input, select {
  width: 100%;
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
}

.value-row {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.value-row input {
  flex: 1;
  margin-right: 10px;
}

.remove-btn {
  background-color: #f44336;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 5px 10px;
  cursor: pointer;
}

.add-btn {
  background-color: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 8px 12px;
  cursor: pointer;
  margin-top: 5px;
}

.preview {
  margin-top: 20px;
  padding: 10px;
  background-color: #eee;
  border-radius: 4px;
}

.frame-hex {
  font-family: monospace;
  letter-spacing: 2px;
}

.byte {
  display: inline-block;
  padding: 3px;
  margin: 2px;
  background-color: #ddd;
  border-radius: 3px;
}

.buttons {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}

.send-btn, .reset-btn {
  padding: 10px 15px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
}

.send-btn {
  background-color: #2196F3;
  color: white;
  flex: 2;
}

.reset-btn {
  background-color: #ff9800;
  color: white;
  flex: 1;
}
</style> 