<template>
  <div class="connections-page">
    <div class="card">
      <div class="card-header">
        <h2>连接管理</h2>
        <el-button type="primary" @click="showCreateDialog">
          <el-icon><Plus /></el-icon>
          新建连接
        </el-button>
      </div>
      
      <el-table :data="connections" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="150">
          <template #default="{ row }">
            <code class="id-code">{{ row.id }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" width="150" />
        <el-table-column prop="url" label="地址" show-overflow-tooltip />
        <el-table-column label="自动重连" width="100">
          <template #default="{ row }">
            <el-tag :type="row.auto_reconnect ? 'success' : 'info'" size="small">
              {{ row.auto_reconnect ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="允许转发" width="100">
          <template #default="{ row }">
            <el-tag :type="row.allow_forward ? 'success' : 'info'" size="small">
              {{ row.allow_forward ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <span :class="['status-tag', row.connected ? 'connected' : 'disconnected']">
              <el-icon v-if="row.connected"><CircleCheck /></el-icon>
              <el-icon v-else><CircleClose /></el-icon>
              {{ row.connected ? '已连接' : '未连接' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250">
          <template #default="{ row }">
            <el-button
              v-if="!row.connected"
              type="success"
              size="small"
              @click="handleConnect(row)"
            >
              连接
            </el-button>
            <el-button
              v-else
              type="warning"
              size="small"
              @click="handleDisconnect(row)"
            >
              断开
            </el-button>
            <el-button type="primary" size="small" @click="showEditDialog(row)">
              编辑
            </el-button>
            <el-button type="danger" size="small" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    
    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑连接' : '新建连接'"
      width="500px"
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="连接名称（如：可爱机器人）" />
        </el-form-item>
        <el-form-item label="地址" required>
          <el-input v-model="form.url" placeholder="ws://localhost:9001/onebot/v11/ws" />
          <div class="form-tip">上游服务的 WebSocket 地址</div>
        </el-form-item>
        <el-form-item label="Token">
          <el-input v-model="form.token" placeholder="OneBot v11 认证 Token（可选）" show-password />
          <div class="form-tip">如果服务需要认证，请填写 Token</div>
        </el-form-item>
        <el-form-item label="自动重连">
          <el-switch v-model="form.auto_reconnect" />
        </el-form-item>
        <el-form-item label="重连间隔" v-if="form.auto_reconnect">
          <el-input-number v-model="form.reconnect_interval" :min="1" :max="60" />
          <span style="margin-left: 10px">秒</span>
        </el-form-item>
        <el-form-item label="允许转发">
          <el-switch v-model="form.allow_forward" />
          <div class="form-tip">开启后，此连接可以主动发起消息并转发到其他连接</div>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">
          {{ isEditing ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { connectionApi } from '../api'

const connections = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEditing = ref(false)
const submitting = ref(false)
const editingId = ref('')

const form = ref({
  name: '',
  url: '',
  token: '',
  auto_reconnect: true,
  reconnect_interval: 5,
  allow_forward: false,
})

// 生成 ID
const generateId = (name) => {
  const base = name
    ? name.toLowerCase().replace(/[^a-z0-9]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '').slice(0, 20)
    : ''
  
  // 如果基础名已经足够唯一且包含非空内容，且长度适中，可以尝试不加后缀（或者让用户必填）
  // 这里为了兼容性，如果名称是纯英文数字，则不加随机后缀，方便用户记忆
  if (/^[a-z0-9-]+$/.test(base) && base.length > 2) {
    return base
  }
  
  const suffix = Date.now().toString(36).slice(-4)
  return base ? `${base}-${suffix}` : `conn-${suffix}`
}

const fetchData = async () => {
  loading.value = true
  try {
    connections.value = await connectionApi.getAll()
  } catch (error) {
    ElMessage.error('加载连接失败')
  } finally {
    loading.value = false
  }
}

const showCreateDialog = () => {
  isEditing.value = false
  form.value = {
    name: '',
    url: '',
    token: '',
    auto_reconnect: true,
    reconnect_interval: 5,
    allow_forward: false,
  }
  dialogVisible.value = true
}

const showEditDialog = (row) => {
  isEditing.value = true
  editingId.value = row.id
  form.value = { ...row }
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入连接名称')
    return
  }
  if (!form.value.url.trim()) {
    ElMessage.warning('请输入连接地址')
    return
  }

  submitting.value = true
  try {
    if (isEditing.value) {
      await connectionApi.update(editingId.value, form.value)
      ElMessage.success('更新成功')
    } else {
      // 自动生成 ID
      const id = generateId(form.value.name)
      await connectionApi.create({ ...form.value, id })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await fetchData()
  } catch (error) {
    console.error('Submit error:', error)
    ElMessage.error(isEditing.value ? '更新失败' : '创建失败')
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除连接「${row.name}」吗？`,
      '确认删除',
      { type: 'warning' }
    )
    
    await connectionApi.delete(row.id)
    ElMessage.success('删除成功')
    await fetchData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleConnect = async (row) => {
  try {
    await connectionApi.connect(row.id)
    ElMessage.success('连接成功')
    await fetchData()
  } catch (error) {
    console.error('Connect error:', error)
    ElMessage.error('连接失败：' + (error.response?.data?.detail || '未知错误'))
  }
}

const handleDisconnect = async (row) => {
  try {
    await connectionApi.disconnect(row.id)
    ElMessage.success('已断开')
    await fetchData()
  } catch (error) {
    ElMessage.error('断开失败')
  }
}

onMounted(fetchData)
</script>

<style scoped>
.form-tip {
  color: #999;
  font-size: 12px;
  margin-top: 5px;
}
.id-code {
  background: #f0f2f5;
  padding: 2px 4px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
}
</style>
