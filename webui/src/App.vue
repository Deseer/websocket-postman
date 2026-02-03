<template>
  <div class="app-container">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <h1>🔌 指令分配器</h1>
        <p>WebSocket Postman</p>
      </div>
      
      <el-menu
        :default-active="currentRoute"
        router
        :collapse="false"
      >
        <el-menu-item index="/dashboard">
          <el-icon><Monitor /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        
        <el-menu-item index="/command-sets">
          <el-icon><Collection /></el-icon>
          <span>指令集管理</span>
        </el-menu-item>
        
        <el-menu-item index="/users">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
        
        <el-menu-item index="/connections">
          <el-icon><Connection /></el-icon>
          <span>连接管理</span>
        </el-menu-item>
        
        <el-menu-item index="/access-lists">
          <el-icon><List /></el-icon>
          <span>黑白名单</span>
        </el-menu-item>
        
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
      </el-menu>
    </aside>
    
    <!-- 主内容区 -->
    <main class="main-content">
      <header class="header">
        <h2>{{ pageTitle }}</h2>
        <div class="header-right">
          <el-button type="primary" text @click="refreshData">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </header>
      
      <div class="content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const currentRoute = computed(() => route.path)

const pageTitle = computed(() => route.meta.title || '仪表盘')

const refreshData = () => {
  window.location.reload()
}
</script>
