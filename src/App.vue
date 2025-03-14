<script setup>
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <header>
    <nav>
      <RouterLink to="/home">普通串口</RouterLink>
      <RouterLink to="/modbus">Modbus协议</RouterLink>
    </nav>
  </header>

  <main>
    <RouterView />
  </main>
</template>

<style scoped>
header {
  background-color: #2c3e50;
  padding: 15px 0;
  margin-bottom: 20px;
}

nav {
  display: flex;
  justify-content: center;
  gap: 20px;
}

nav a {
  color: white;
  text-decoration: none;
  padding: 10px 15px;
  border-radius: 4px;
  font-weight: bold;
  transition: background-color 0.3s;
}

nav a:hover {
  background-color: #34495e;
}

nav a.router-link-active {
  background-color: #3498db;
}
</style>