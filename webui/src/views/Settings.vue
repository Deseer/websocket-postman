<template>
  <div class="settings-page">
    <el-tabs v-model="activeTab">
      <!-- 服务器配置 -->
      <el-tab-pane label="服务器配置" name="server">
        <div class="card">
          <el-form :model="serverForm" label-width="140px">
            <el-form-item label="HTTP 监听地址">
              <el-input v-model="serverForm.host" placeholder="0.0.0.0" style="width: 200px" />
            </el-form-item>
            <el-form-item label="HTTP 端口">
              <el-input-number v-model="serverForm.port" :min="1" :max="65535" />
            </el-form-item>
            <el-form-item label="WebSocket 端口">
              <el-input-number v-model="serverForm.ws_port" :min="1" :max="65535" />
              <div class="form-tip">NapCat 连接到此端口</div>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>

      <!-- 管理员配置 -->
      <el-tab-pane label="管理员" name="admins">
        <div class="card">
          <div class="section-header">
            <h3>管理员 QQ 号</h3>
            <el-button type="primary" size="small" @click="addAdmin">
              <el-icon><Plus /></el-icon>
              添加
            </el-button>
          </div>
          <div v-if="admins.length === 0" class="empty-tip">暂无管理员</div>
          <div v-for="(admin, index) in admins" :key="index" class="admin-item">
            <el-input-number
              v-model="admins[index]"
              :controls="false"
              placeholder="输入 QQ 号"
              style="width: 200px"
            />
            <el-button type="danger" size="small" @click="removeAdmin(index)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>
      </el-tab-pane>

      <!-- 数据库配置 -->
      <el-tab-pane label="数据库" name="database">
        <div class="card">
          <el-form :model="databaseForm" label-width="140px">
            <el-form-item label="数据库 URL">
              <el-input v-model="databaseForm.url" placeholder="sqlite+aiosqlite:///./data/dispatcher.db" style="width: 400px" />
              <div class="form-tip">支持 SQLite 和其他 SQLAlchemy 兼容的数据库</div>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>

      <!-- 日志配置 -->
      <el-tab-pane label="日志设置" name="logging">
        <div class="card">
          <el-form :model="loggingForm" label-width="140px">
            <el-form-item label="日志级别">
              <el-select v-model="loggingForm.level" style="width: 150px">
                <el-option label="DEBUG" value="DEBUG" />
                <el-option label="INFO" value="INFO" />
                <el-option label="WARNING" value="WARNING" />
                <el-option label="ERROR" value="ERROR" />
              </el-select>
            </el-form-item>
            <el-form-item label="日志文件">
              <el-input v-model="loggingForm.file" placeholder="./logs/dispatcher.log" style="width: 300px" />
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>

      <!-- 日志查看 -->
      <el-tab-pane label="日志查看" name="logs">
        <div class="card logs-card">
          <div class="logs-header">
            <el-select v-model="logLevel" placeholder="日志级别" style="width: 120px" size="small">
              <el-option label="全部" value="" />
              <el-option label="DEBUG" value="DEBUG" />
              <el-option label="INFO" value="INFO" />
              <el-option label="WARNING" value="WARNING" />
              <el-option label="ERROR" value="ERROR" />
            </el-select>
            <el-switch v-model="realTimeMode" active-text="实时" inactive-text="手动" style="margin-left: 10px" @change="toggleRealTime" />
            <el-button type="primary" size="small" @click="fetchLogs" :loading="loadingLogs" v-if="!realTimeMode">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
            <el-tag v-else :type="wsConnected ? 'success' : 'danger'" size="small">
              {{ wsConnected ? '已连接' : '未连接' }}
            </el-tag>
            <el-button size="small" @click="clearLogs">
              清空显示
            </el-button>
          </div>
          <div class="logs-container" ref="logsContainer">
            <div v-if="logs.length === 0" class="empty-tip">暂无日志</div>
            <div
              v-for="(log, index) in filteredLogs"
              :key="index"
              :class="['log-line', `log-${log.level?.toLowerCase()}`]"
            >
              <span class="log-time">{{ log.time }}</span>
              <span class="log-level">{{ log.level }}</span>
              <span class="log-message">{{ log.message }}</span>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- Final 规则 -->
      <el-tab-pane label="默认规则" name="final">
        <div class="card">
          <el-form :model="finalForm" label-width="140px">
            <el-form-item label="未匹配指令处理">
              <el-select v-model="finalForm.action" style="width: 150px">
                <el-option label="拒绝" value="reject" />
                <el-option label="允许" value="allow" />
                <el-option label="转发" value="forward" />
              </el-select>
            </el-form-item>
            <el-form-item label="目标连接" v-if="finalForm.action === 'forward'">
              <el-select v-model="finalForm.target_ws" placeholder="选择连接" style="width: 200px">
                <el-option
                  v-for="conn in connections"
                  :key="conn.id"
                  :label="conn.name"
                  :value="conn.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="发送拒绝消息" v-if="finalForm.action === 'reject'">
              <el-switch v-model="finalForm.send_message" />
              <div class="form-tip">关闭后，未匹配的指令将被静默忽略</div>
            </el-form-item>
            <el-form-item label="拒绝消息" v-if="finalForm.action === 'reject' && finalForm.send_message">
              <el-input v-model="finalForm.message" placeholder="未知指令" style="width: 400px" />
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 保存按钮 -->
    <div class="save-bar" v-if="activeTab !== 'logs'">
      <el-button type="primary" size="large" @click="saveConfig" :loading="saving">
        <el-icon><Check /></el-icon>
        保存配置
      </el-button>
      <span class="save-tip">修改后需要重启服务才能生效</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { configApi, connectionApi, monitorApi } from '../api'

const activeTab = ref('server')
const saving = ref(false)
const connections = ref([])

// 表单数据
const serverForm = ref({
  host: '0.0.0.0',
  port: 8080,
  ws_port: 8765,
})

const databaseForm = ref({
  url: 'sqlite+aiosqlite:///./data/dispatcher.db',
})

const loggingForm = ref({
  level: 'INFO',
  file: './logs/dispatcher.log',
})

const finalForm = ref({
  action: 'reject',
  target_ws: '',
  message: '未知指令，请使用 /help 查看帮助',
  send_message: true,
})

const admins = ref([])

// 日志相关
const logs = ref([])
const logLevel = ref('')
const loadingLogs = ref(false)
const logsContainer = ref(null)
const realTimeMode = ref(true)
const wsConnected = ref(false)
let logWebSocket = null
const MAX_LOGS = 500  // 最多保留的日志条数

const filteredLogs = computed(() => {
  if (!logLevel.value) return logs.value
  return logs.value.filter(log => log.level === logLevel.value)
})

// 加载配置
const fetchConfig = async () => {
  try {
    const [config, connRes] = await Promise.all([
      configApi.get(),
      connectionApi.getAll(),
    ])
    
    connections.value = connRes
    
    if (config.server) {
      serverForm.value = { ...config.server }
    }
    if (config.database) {
      databaseForm.value = { ...config.database }
    }
    if (config.logging) {
      loggingForm.value = { ...config.logging }
    }
    if (config.final) {
      finalForm.value = { ...config.final }
    }
    if (config.admins) {
      admins.value = [...config.admins]
    }
  } catch (error) {
    console.error('Load config error:', error)
    ElMessage.error('加载配置失败')
  }
}

// 加载日志
const fetchLogs = async () => {
  loadingLogs.value = true
  try {
    const res = await monitorApi.getLogs()
    logs.value = res || []
    await nextTick()
    scrollToBottom()
  } catch (error) {
    console.error('Load logs error:', error)
    ElMessage.error('加载日志失败')
  } finally {
    loadingLogs.value = false
  }
}

const scrollToBottom = () => {
  if (logsContainer.value) {
    logsContainer.value.scrollTop = logsContainer.value.scrollHeight
  }
}

const clearLogs = () => {
  logs.value = []
}

// WebSocket 实时日志
const connectLogWebSocket = () => {
  if (logWebSocket) {
    logWebSocket.close()
  }
  
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/ws/logs`
  
  logWebSocket = new WebSocket(wsUrl)
  
  logWebSocket.onopen = () => {
    wsConnected.value = true
    logs.value = []  // 清空旧日志
  }
  
  logWebSocket.onmessage = (event) => {
    try {
      const log = JSON.parse(event.data)
      if (log.error) {
        ElMessage.error(log.error)
        return
      }
      logs.value.push(log)
      // 限制日志数量
      if (logs.value.length > MAX_LOGS) {
        logs.value = logs.value.slice(-MAX_LOGS)
      }
      nextTick(scrollToBottom)
    } catch (e) {
      console.error('Parse log error:', e)
    }
  }
  
  logWebSocket.onclose = () => {
    wsConnected.value = false
    // 实时模式下自动重连
    if (realTimeMode.value) {
      setTimeout(connectLogWebSocket, 3000)
    }
  }
  
  logWebSocket.onerror = () => {
    wsConnected.value = false
  }
}

const disconnectLogWebSocket = () => {
  if (logWebSocket) {
    logWebSocket.close()
    logWebSocket = null
  }
  wsConnected.value = false
}

const toggleRealTime = (value) => {
  if (value) {
    connectLogWebSocket()
  } else {
    disconnectLogWebSocket()
    fetchLogs()
  }
}

// 管理员操作
const addAdmin = () => {
  admins.value.push(0)
}

const removeAdmin = (index) => {
  admins.value.splice(index, 1)
}

// 保存配置
const saveConfig = async () => {
  saving.value = true
  try {
    await configApi.update({
      server: serverForm.value,
      database: databaseForm.value,
      logging: loggingForm.value,
      final: finalForm.value,
      admins: admins.value.filter(a => a > 0),
    })
    ElMessage.success('配置保存成功，请重启服务使配置生效')
  } catch (error) {
    console.error('Save config error:', error)
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchConfig()
  // 默认实时模式，自动连接 WebSocket
  if (realTimeMode.value) {
    connectLogWebSocket()
  }
})

import { onUnmounted } from 'vue'
onUnmounted(() => {
  disconnectLogWebSocket()
})
</script>

<style scoped>
.settings-page {
  padding-bottom: 80px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.section-header h3 {
  margin: 0;
}

.admin-item {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
}

.empty-tip {
  color: #999;
  padding: 20px;
  text-align: center;
}

.form-tip {
  color: #999;
  font-size: 12px;
  margin-top: 5px;
}

.save-bar {
  position: fixed;
  bottom: 0;
  left: 220px;
  right: 0;
  background: #fff;
  padding: 15px 30px;
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
  gap: 15px;
  z-index: 100;
}

.save-tip {
  color: #999;
  font-size: 13px;
}

/* 日志样式 */
.logs-card {
  padding: 0 !important;
}

.logs-header {
  display: flex;
  gap: 10px;
  padding: 15px;
  border-bottom: 1px solid #eee;
  background: #fafafa;
}

.logs-container {
  height: 500px;
  overflow-y: auto;
  padding: 10px;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 12px;
  background: #1e1e1e;
  color: #d4d4d4;
}

.log-line {
  padding: 3px 0;
  white-space: nowrap;
}

.log-time {
  color: #888;
  margin-right: 10px;
}

.log-level {
  display: inline-block;
  width: 60px;
  font-weight: bold;
}

.log-message {
  color: #fff;
}

.log-debug .log-level { color: #9cdcfe; }
.log-info .log-level { color: #4ec9b0; }
.log-warning .log-level { color: #dcdcaa; }
.log-error .log-level { color: #f14c4c; }
</style>
