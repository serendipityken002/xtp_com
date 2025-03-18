<template>
  <div class="modbus-view">
    <h1>基于modbus协议读取三台通风柜数据</h1>
    <home />
  </div>
</template>

<script setup>
// import ModbusInterface from '../components/ModbusInterface.vue';
import home from '../components/home.vue';

</script>

<style scoped>
.modbus-view {
  padding: 20px;
  max-width: 1600px;
  margin: 0 auto;
}

h1 {
  text-align: center;
  margin-bottom: 30px;
  color: #2c3e50;
}
</style> 