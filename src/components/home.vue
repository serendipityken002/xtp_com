<template>
  <div class="ventilation-cabinets">
    <div v-for="(cabinet, index) in cabinets" :key="index" class="cabinet">
      <h2>排风柜 {{ index + 1 }}</h2>
      <p><strong>总控开关:</strong> {{ cabinet.masterSwitch ? '开' : '关' }}</p>
      <p><strong>灯光开关:</strong> {{ cabinet.lightSwitch ? '开' : '关' }}</p>
      <p><strong>风扇风速:</strong> {{ cabinet.fanSpeed }} rpm</p>
      <p><strong>室内温度:</strong> {{ cabinet.roomTemperature }} °C</p>
    </div>
    <button @click="auto_receive">接收数据</button>
  </div>
</template>

<script setup>
import axios from 'axios';
import { ref } from 'vue';

// 假设这是从服务器获取的数据
const cabinets = ref([
  {
    masterSwitch: true,
    lightSwitch: false,
    fanSpeed: 1200,
    roomTemperature: 22.5,
  },
  {
    masterSwitch: false,
    lightSwitch: true,
    fanSpeed: 900,
    roomTemperature: 24.0,
  },
  {
    masterSwitch: true,
    lightSwitch: true,
    fanSpeed: 1100,
    roomTemperature: 23.0,
  },
]);

const port_name = 'COM10';
const requests = ref([
    {
        "slave_address": 1,
        "function_code": 3,
        "start_address": 2,
        "quantity": 4
    },
    {
        "slave_address": 2,
        "function_code": 3,
        "start_address": 2,
        "quantity": 4
    },
    {
        "slave_address": 3,
        "function_code": 3,
        "start_address": 2,
        "quantity": 4
    }
])

const auto_receive = async () => { 
    const response = await axios.post('http://127.0.0.1:5000/send_data',     {
        "slave_address": 1,
        "function_code": 3,
        "start_address": 2,
        "quantity": 4
    });
    console.log(response.data);
}

// const auto_receive = async () => { 
//     try {
//         const response = await axios.post('http://127.0.0.1:5000/api/modbus/send', { 
//             'port_name': port_name, 
//             'requests': requests.value 
//         });

//         const serverData = response.data.results;

//         // 根据slave_address匹配并更新cabinets
//         serverData.forEach(serverItem => {
//             const cabinetIndex = serverItem.slave_address - 1; // 假设slave_address与cabinets索引对应
//             if (cabinetIndex >= 0 && cabinetIndex < cabinets.value.length) {
//                 cabinets.value[cabinetIndex].masterSwitch = serverItem.data[0];
//                 cabinets.value[cabinetIndex].lightSwitch = serverItem.data[1];
//                 cabinets.value[cabinetIndex].fanSpeed = serverItem.data[2];
//                 cabinets.value[cabinetIndex].roomTemperature = serverItem.data[3];
//             }
//         });

//         console.log(cabinets.value);
//     } catch (error) {
//         console.error("There was an error sending the request!", error);
//     }
// }
// 每三秒秒接收一次数据
// setInterval(auto_receive(), 3000)

// 调用一次auto_receive
// auto_receive()

</script>

<style scoped>
.ventilation-cabinets {
  display: flex;
  justify-content: space-around;
}
.cabinet {
  border: 1px solid #ccc;
  padding: 1em;
  width: 25%;
  text-align: left;
}
</style>