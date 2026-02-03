<template>
  <div class="categories-page">
    <div class="card">
      <div class="card-header">
        <h2>分类管理</h2>
        <el-button type="primary" @click="showCreateDialog">
          <el-icon><Plus /></el-icon>
          新建分类
        </el-button>
      </div>
      
      <el-table :data="categories" stripe v-loading="loading">
        <el-table-column prop="display_name" label="显示名称" />
        <el-table-column prop="name" label="标识名" width="150" />
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column prop="order" label="排序" width="80" />
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
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
      :title="isEditing ? '编辑分类' : '新建分类'"
      width="500px"
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="分类 ID" v-if="!isEditing">
          <el-input v-model="form.id" placeholder="唯一标识，如 bot" />
        </el-form-item>
        <el-form-item label="标识名">
          <el-input v-model="form.name" placeholder="用于指令，如 bot" />
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input v-model="form.display_name" placeholder="如 聊天机器人" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="4"
            placeholder="分类的详细介绍"
          />
        </el-form-item>
        <el-form-item label="图标">
          <el-input v-model="form.icon" placeholder="可选，emoji 或图标" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.order" :min="0" :max="999" />
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
import { categoryApi } from '../api'

const categories = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEditing = ref(false)
const submitting = ref(false)
const editingId = ref('')

const form = ref({
  id: '',
  name: '',
  display_name: '',
  description: '',
  icon: '',
  order: 0,
})

const fetchData = async () => {
  loading.value = true
  try {
    categories.value = await categoryApi.getAll()
  } catch (error) {
    ElMessage.error('加载分类失败')
  } finally {
    loading.value = false
  }
}

const showCreateDialog = () => {
  isEditing.value = false
  form.value = {
    id: '',
    name: '',
    display_name: '',
    description: '',
    icon: '',
    order: 0,
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
  submitting.value = true
  try {
    if (isEditing.value) {
      await categoryApi.update(editingId.value, form.value)
      ElMessage.success('更新成功')
    } else {
      await categoryApi.create(form.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await fetchData()
  } catch (error) {
    ElMessage.error(isEditing.value ? '更新失败' : '创建失败')
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除分类「${row.display_name}」吗？`,
      '确认删除',
      { type: 'warning' }
    )
    
    await categoryApi.delete(row.id)
    ElMessage.success('删除成功')
    await fetchData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(fetchData)
</script>
