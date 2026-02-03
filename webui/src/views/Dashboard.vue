<template>
  <div class="dashboard">
    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon primary">
          <el-icon><Connection /></el-icon>
        </div>
        <div class="stat-info">
          <h3>{{ stats.connections?.connected || 0 }} / {{ stats.connections?.total || 0 }}</h3>
          <p>WebSocket 连接</p>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon success">
          <el-icon><ChatDotRound /></el-icon>
        </div>
        <div class="stat-info">
          <h3>{{ stats.messages?.today || 0 }}</h3>
          <p>今日消息</p>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon info">
          <el-icon><Collection /></el-icon>
        </div>
        <div class="stat-info">
          <h3>{{ commandSets.length }}</h3>
          <p>指令集</p>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon warning">
          <el-icon><Folder /></el-icon>
        </div>
        <div class="stat-info">
          <h3>{{ categories.length }}</h3>
          <p>分类</p>
        </div>
      </div>
    </div>
    
    <!-- 连接状态 -->
    <div class="card">
      <div class="card-header">
        <h2>连接状态</h2>
        <el-button type="primary" size="small" @click="refreshConnections">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
      
      <el-table :data="connections" stripe>
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="url" label="地址" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <span :class="['status-tag', row.connected ? 'connected' : 'disconnected']">
              <el-icon v-if="row.connected"><CircleCheck /></el-icon>
              <el-icon v-else><CircleClose /></el-icon>
              {{ row.connected ? '已连接' : '未连接' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button
              v-if="!row.connected"
              type="primary"
              size="small"
              @click="connectWs(row.id)"
            >
              连接
            </el-button>
            <el-button
              v-else
              type="danger"
              size="small"
              @click="disconnectWs(row.id)"
            >
              断开
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    
    <!-- 指令集概览 -->
    <div class="card">
      <div class="card-header">
        <h2>指令集概览</h2>
        <el-button type="primary" size="small" @click="$router.push('/command-sets')">
          管理指令集
        </el-button>
      </div>
      
      <el-table :data="commandSets" stripe>
        <el-table-column prop="name" label="名称" />
        <el-table-column label="分类">
          <template #default="{ row }">
            {{ getCategoryName(row.category) }}
          </template>
        </el-table-column>
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.is_public" type="success" size="small">公共</el-tag>
            <el-tag v-else-if="row.mutual_exclusive_group" type="warning" size="small">
              互斥
            </el-tag>
            <el-tag v-else type="info" size="small">普通</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="目标连接">
          <template #default="{ row }">
            {{ getConnectionName(row.target_ws) }}
          </template>
        </el-table-column>
        <el-table-column label="指令数" width="100">
          <template #default="{ row }">
            {{ row.commands?.length || 0 }}
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { monitorApi, connectionApi, commandSetApi, categoryApi } from '../api'

const stats = ref({})
const connections = ref([])
const commandSets = ref([])
const categories = ref([])

const fetchData = async () => {
  try {
    const [statsRes, connRes, csRes, catRes] = await Promise.all([
      monitorApi.getStats(),
      connectionApi.getAll(),
      commandSetApi.getAll(),
      categoryApi.getAll(),
    ])
    
    stats.value = statsRes
    connections.value = connRes
    commandSets.value = csRes
    categories.value = catRes
  } catch (error) {
    ElMessage.error('加载数据失败')
    console.error(error)
  }
}

// 根据分类 ID 获取显示名称
const getCategoryName = (categoryId) => {
  if (!categoryId) return '-'
  const cat = categories.value.find(c => c.id === categoryId)
  return cat ? cat.display_name : categoryId
}

// 根据连接 ID 获取连接名称
const getConnectionName = (connId) => {
  if (!connId) return '-'
  const conn = connections.value.find(c => c.id === connId)
  return conn ? conn.name : connId
}

const refreshConnections = async () => {
  try {
    connections.value = await connectionApi.getAll()
    ElMessage.success('刷新成功')
  } catch (error) {
    ElMessage.error('刷新失败')
  }
}

const connectWs = async (id) => {
  try {
    await connectionApi.connect(id)
    ElMessage.success('连接成功')
    await refreshConnections()
  } catch (error) {
    ElMessage.error('连接失败')
  }
}

const disconnectWs = async (id) => {
  try {
    await connectionApi.disconnect(id)
    ElMessage.success('已断开连接')
    await refreshConnections()
  } catch (error) {
    ElMessage.error('断开失败')
  }
}

onMounted(fetchData)
</script>
