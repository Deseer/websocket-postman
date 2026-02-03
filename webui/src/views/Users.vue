<template>
  <div class="users-page">
    <div class="card">
      <div class="card-header">
        <h2>用户管理</h2>
        <el-input
          v-model="searchId"
          placeholder="输入 QQ 号搜索"
          style="width: 200px"
          @keyup.enter="searchUser"
        >
          <template #append>
            <el-button @click="searchUser">
              <el-icon><Search /></el-icon>
            </el-button>
          </template>
        </el-input>
      </div>
      
      <el-table :data="users" stripe v-loading="loading">
        <el-table-column prop="qq_id" label="QQ 号" width="150" />
        <el-table-column prop="nickname" label="昵称" width="150" />
        <el-table-column label="权限" width="150">
          <template #default="{ row }">
            <el-tag v-if="row.is_admin" type="danger" size="small">管理员</el-tag>
            <el-tag v-if="row.is_privileged" type="warning" size="small">特权</el-tag>
            <el-tag v-if="!row.is_admin && !row.is_privileged" type="info" size="small">
              普通
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="已选风格" min-width="200">
          <template #default="{ row }">
            <el-tag
              v-for="(style, group) in row.selected_styles || {}"
              :key="group"
              size="small"
              type="success"
              style="margin-right: 5px"
            >
              {{ getCategoryName(group) }}: {{ getStyleName(style) }}
            </el-tag>
            <span v-if="!Object.keys(row.selected_styles || {}).length" style="color: #999">
              未选择
            </span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="showEditDialog(row)">
              编辑
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <div style="margin-top: 20px; text-align: right">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </div>
    
    <!-- 编辑对话框 -->
    <el-dialog v-model="dialogVisible" title="编辑用户" width="600px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="QQ 号">
          <el-input v-model="form.qq_id" disabled />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="form.nickname" />
        </el-form-item>
        <el-form-item label="特权用户">
          <el-switch v-model="form.is_privileged" />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { userApi, commandSetApi, categoryApi } from '../api'

const users = ref([])
const commandSets = ref([])
const categories = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const submitting = ref(false)
const searchId = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

const form = ref({
  qq_id: 0,
  nickname: '',
  is_privileged: false,
})



const fetchData = async () => {
  loading.value = true
  try {
    const skip = (currentPage.value - 1) * pageSize.value
    const [usersRes, csRes, catRes] = await Promise.all([
      userApi.getAll(skip, pageSize.value),
      commandSetApi.getAll(),
      categoryApi.getAll(),
    ])
    users.value = usersRes
    commandSets.value = csRes
    categories.value = catRes
    total.value = usersRes.length // 简化处理
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

// 获取分类显示名称
const getCategoryName = (categoryId) => {
  if (!categoryId) return categoryId
  const cat = categories.value.find(c => c.id === categoryId)
  return cat ? cat.display_name : categoryId
}

// 获取指令集名称
const getStyleName = (styleId) => {
  if (!styleId) return styleId
  const cs = commandSets.value.find(c => c.id === styleId)
  return cs ? cs.name : styleId
}

const searchUser = async () => {
  if (!searchId.value) {
    await fetchData()
    return
  }
  
  loading.value = true
  try {
    const user = await userApi.get(parseInt(searchId.value))
    users.value = [user]
  } catch (error) {
    ElMessage.warning('未找到该用户')
    users.value = []
  } finally {
    loading.value = false
  }
}

const showEditDialog = (row) => {
  form.value = {
    qq_id: row.qq_id,
    nickname: row.nickname || '',
    is_privileged: row.is_privileged || false,
  }
  dialogVisible.value = true
}

const handleSubmit = async () => {
  submitting.value = true
  try {
    await userApi.update(form.value.qq_id, form.value)
    ElMessage.success('更新成功')
    dialogVisible.value = false
    await fetchData()
  } catch (error) {
    ElMessage.error('更新失败')
  } finally {
    submitting.value = false
  }
}

const handlePageChange = (page) => {
  currentPage.value = page
  fetchData()
}

onMounted(fetchData)
</script>
