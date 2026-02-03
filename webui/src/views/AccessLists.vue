<template>
  <div class="access-lists-page">
    <div class="action-bar">
      <el-button type="primary" @click="showCreateDialog">
        <el-icon><Plus /></el-icon>
        新建黑白名单
      </el-button>
    </div>

    <!-- 用户黑白名单 -->
    <div class="card">
      <div class="card-header">
        <h2>用户黑白名单</h2>
      </div>
      <el-table :data="userLists" stripe v-loading="loading">
        <el-table-column prop="name" label="名称" min-width="200" />
        <el-table-column label="模式" width="120">
          <template #default="{ row }">
            <el-tag :type="row.mode === 'whitelist' ? 'success' : 'danger'" size="small">
              {{ row.mode === 'whitelist' ? '白名单' : '黑名单' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="成员数" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.items?.length || 0 }} 人</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="showEditDialog(row)">编辑</el-button>
            <el-button type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 群聊黑白名单 -->
    <div class="card">
      <div class="card-header">
        <h2>群聊黑白名单</h2>
      </div>
      <el-table :data="groupLists" stripe v-loading="loading">
        <el-table-column prop="name" label="名称" min-width="200" />
        <el-table-column label="模式" width="120">
          <template #default="{ row }">
            <el-tag :type="row.mode === 'whitelist' ? 'success' : 'danger'" size="small">
              {{ row.mode === 'whitelist' ? '白名单' : '黑名单' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="成员数" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.items?.length || 0 }} 个群</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="showEditDialog(row)">编辑</el-button>
            <el-button type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑黑白名单' : '新建黑白名单'"
      width="500px"
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如 VIP 用户" />
        </el-form-item>
        <el-form-item label="类型" required>
          <el-radio-group v-model="form.type">
            <el-radio value="user">用户</el-radio>
            <el-radio value="group">群聊</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="模式" required>
          <el-radio-group v-model="form.mode">
            <el-radio value="whitelist">白名单</el-radio>
            <el-radio value="blacklist">黑名单</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="form.type === 'user' ? 'QQ 号列表' : '群号列表'">
          <el-input
            v-model="itemsInput"
            type="textarea"
            :rows="4"
            :placeholder="form.type === 'user' ? '每行一个 QQ 号' : '每行一个群号'"
          />
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
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { accessListApi } from '../api'

const accessLists = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref('')
const submitting = ref(false)
const itemsInput = ref('')

const form = ref({
  id: '',
  name: '',
  type: 'user',
  mode: 'whitelist',
})

// 分类显示
const userLists = computed(() => accessLists.value.filter(al => al.type === 'user'))
const groupLists = computed(() => accessLists.value.filter(al => al.type === 'group'))

const generateId = (name) => {
  const base = name
    ? name.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fa5]/g, '-').replace(/-+/g, '-').slice(0, 20)
    : ''
  const suffix = Date.now().toString(36).slice(-4)
  return base ? `${base}-${suffix}` : `list-${suffix}`
}

const fetchData = async () => {
  loading.value = true
  try {
    accessLists.value = await accessListApi.getAll()
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const showCreateDialog = () => {
  isEditing.value = false
  editingId.value = ''
  form.value = { id: '', name: '', type: 'user', mode: 'whitelist' }
  itemsInput.value = ''
  dialogVisible.value = true
}

const showEditDialog = (row) => {
  isEditing.value = true
  editingId.value = row.id
  form.value = {
    id: row.id,
    name: row.name,
    type: row.type,
    mode: row.mode,
  }
  itemsInput.value = (row.items || []).join('\n')
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!form.value.name) {
    ElMessage.warning('请输入名称')
    return
  }

  submitting.value = true
  try {
    const items = itemsInput.value
      .split('\n')
      .map(line => line.trim())
      .filter(line => line && /^\d+$/.test(line))
      .map(Number)

    if (isEditing.value) {
      await accessListApi.update(editingId.value, {
        name: form.value.name,
        type: form.value.type,
        mode: form.value.mode,
        items,
      })
      ElMessage.success('更新成功')
    } else {
      const id = generateId(form.value.name)
      await accessListApi.create({
        id,
        name: form.value.name,
        type: form.value.type,
        mode: form.value.mode,
        items,
      })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await fetchData()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除 "${row.name}" 吗？`, '确认删除', {
      type: 'warning',
    })
    await accessListApi.delete(row.id)
    ElMessage.success('删除成功')
    await fetchData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}



onMounted(fetchData)
</script>

<style scoped>
.access-lists-page {
  padding: 20px;
}

.action-bar {
  margin-bottom: 20px;
}

.card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.card-header {
  margin-bottom: 15px;
}

.card-header h2 {
  margin: 0;
  font-size: 18px;
  color: #303133;
}


</style>
