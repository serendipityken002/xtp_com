<template>
  <div class="modbus-view">
    <h1>Modbus协议测试工具</h1>
    <ModbusInterface />
  </div>
</template>

<script setup>
import ModbusInterface from '../components/ModbusInterface.vue';

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