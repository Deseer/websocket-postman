<template>
  <div class="command-sets-page">
    <!-- 操作栏 -->
    <div class="action-bar">
      <el-button type="primary" @click="showCreateCategoryDialog">
        <el-icon><FolderAdd /></el-icon>
        新建分类
      </el-button>
      <el-button type="success" @click="showCreateCommandSetDialog">
        <el-icon><Plus /></el-icon>
        新建指令集
      </el-button>
    </div>

    <!-- 未分类指令集 -->
    <div class="card" v-if="uncategorizedSets.length > 0">
      <div class="card-header category-header">
        <div class="category-title">
          <span class="category-icon">📦</span>
          <h3>未分类</h3>
          <el-tag size="small" type="info">{{ uncategorizedSets.length }} 个指令集</el-tag>
        </div>
      </div>
      <el-table :data="uncategorizedSets" stripe v-loading="loading">
        <el-table-column prop="name" label="名称" width="150" />
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column label="目标连接" width="150">
          <template #default="{ row }">
            {{ getConnectionName(row.target_ws) }}
          </template>
        </el-table-column>
        <el-table-column label="指令" width="80">
          <template #default="{ row }">
            <el-tag size="small">{{ row.commands?.length || 0 }} 个</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="showEditCommandSetDialog(row)">
              编辑
            </el-button>
            <el-button type="danger" size="small" @click="handleDeleteCommandSet(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分类及其指令集 -->
    <div
      class="card"
      v-for="category in categoriesWithSets"
      :key="category.id"
    >
      <div class="card-header category-header">
        <div class="category-title">
          <span class="category-icon">{{ category.icon || '📁' }}</span>
          <h3>{{ category.display_name }}</h3>
          <el-tag size="small" type="info">{{ category.commandSets.length }} 个指令集</el-tag>
        </div>
        <div class="category-actions">
          <el-button type="primary" size="small" text @click="showEditCategoryDialog(category)">
            <el-icon><Edit /></el-icon>
            编辑分类
          </el-button>
          <el-button
            type="danger"
            size="small"
            text
            @click="handleDeleteCategory(category)"
            :disabled="category.commandSets.length > 0"
          >
            <el-icon><Delete /></el-icon>
            删除
          </el-button>
        </div>
      </div>
      <p class="category-description" v-if="category.description">
        {{ category.description }}
      </p>
      <el-table :data="category.commandSets" stripe v-loading="loading">
        <el-table-column prop="name" label="名称" width="150" />
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column label="目标连接" width="150">
          <template #default="{ row }">
            {{ getConnectionName(row.target_ws) }}
          </template>
        </el-table-column>
        <el-table-column label="指令" width="80">
          <template #default="{ row }">
            <el-tag size="small">{{ row.commands?.length || 0 }} 个</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="showEditCommandSetDialog(row)">
              编辑
            </el-button>
            <el-button type="danger" size="small" @click="handleDeleteCommandSet(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="category.commandSets.length === 0" description="暂无指令集" />
    </div>

    <!-- 分类对话框 - 简化版 -->
    <el-dialog
      v-model="categoryDialogVisible"
      :title="isEditingCategory ? '编辑分类' : '新建分类'"
      width="450px"
    >
      <el-form :model="categoryForm" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="categoryForm.display_name" placeholder="如 聊天机器人" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="categoryForm.description"
            type="textarea"
            :rows="2"
            placeholder="分类的详细介绍（可选）"
          />
        </el-form-item>
        <el-form-item label="默认风格">
          <el-select v-model="categoryForm.default_command_set" placeholder="选择默认指令集" clearable style="width: 100%">
            <el-option
              v-for="cs in commandSets.filter(cs => cs.category === categoryForm.id || !cs.category)"
              :key="cs.id"
              :label="cs.name"
              :value="cs.id"
            />
          </el-select>
        </el-form-item>
        <el-row :gutter="10">
          <el-col :span="8">
            <el-form-item label="启用">
              <el-switch v-model="categoryForm.enabled" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="启用互斥">
              <el-switch v-model="categoryForm.is_mutex" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="允许切换">
              <el-switch v-model="categoryForm.allow_user_switch" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="categoryDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCategorySubmit" :loading="submitting">
          {{ isEditingCategory ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 指令集对话框 - 简化版 -->
    <el-dialog
      v-model="commandSetDialogVisible"
      :title="isEditingCommandSet ? '编辑指令集' : '新建指令集'"
      width="600px"
    >
      <el-form :model="commandSetForm" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="commandSetForm.name" placeholder="指令集名称" />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="分类">
              <el-select v-model="commandSetForm.category" placeholder="选择分类（可留空）" clearable style="width: 100%">
                <el-option
                  v-for="cat in categories"
                  :key="cat.id"
                  :label="cat.display_name"
                  :value="cat.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="目标连接">
              <el-select v-model="commandSetForm.target_ws" placeholder="选择连接（可选）" clearable style="width: 100%">
                <el-option
                  v-for="conn in connections"
                  :key="conn.id"
                  :label="conn.name"
                  :value="conn.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="描述">
          <el-input v-model="commandSetForm.description" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>

        <el-form-item label="启用">
          <el-switch v-model="commandSetForm.enabled" />
          <span style="margin-left: 10px; color: #909399; font-size: 12px">禁用后该指令集不会被匹配</span>
        </el-form-item>

        <!-- 高级选项 - 折叠 -->
        <el-collapse v-model="advancedExpanded">
          <el-collapse-item title="高级选项" name="advanced">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="前缀">
                  <el-input v-model="commandSetForm.prefix" placeholder="用于前缀调用" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="公共指令集">
                  <el-switch v-model="commandSetForm.is_public" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="剥离前缀">
                  <el-switch v-model="commandSetForm.strip_prefix" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="优先级">
                  <el-input-number v-model="commandSetForm.priority" :min="0" :max="999" size="small" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="默认指令集">
                  <el-switch v-model="commandSetForm.is_default" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="用户名单">
                  <el-select v-model="commandSetForm.user_access_list" placeholder="选择用户黑白名单" clearable style="width: 100%">
                    <el-option
                      v-for="al in userAccessLists"
                      :key="al.id"
                      :label="`${al.name} (${al.mode === 'whitelist' ? '白名单' : '黑名单'})`"
                      :value="al.id"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="群聊名单">
                  <el-select v-model="commandSetForm.group_access_list" placeholder="选择群聊黑白名单" clearable style="width: 100%">
                    <el-option
                      v-for="al in groupAccessLists"
                      :key="al.id"
                      :label="`${al.name} (${al.mode === 'whitelist' ? '白名单' : '黑名单'})`"
                      :value="al.id"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <!-- 指令列表 -->
            <el-form-item label="指令列表">
              <div class="commands-editor">
                <div
                  v-for="(cmd, index) in commandSetForm.commands"
                  :key="index"
                  class="command-item"
                >
                  <div class="command-row">
                    <el-input v-model="cmd.name" placeholder="/指令名" style="width: 120px" />
                    <el-input v-model="cmd.description" placeholder="描述" style="width: 180px" />
                    <el-checkbox v-model="cmd.is_privileged">特权</el-checkbox>
                    <el-button type="danger" size="small" @click="removeCommand(index)">
                      <el-icon><Delete /></el-icon>
                    </el-button>
                  </div>
                  <div class="command-options">
                    <el-checkbox v-model="cmd.hasTimeRestriction" @change="toggleTimeRestriction(cmd)">
                      时间限制
                    </el-checkbox>
                    <template v-if="cmd.hasTimeRestriction">
                      <el-time-select
                        v-model="cmd.time_start"
                        :max-time="cmd.time_end"
                        placeholder="开始时间"
                        start="00:00"
                        step="00:30"
                        end="23:30"
                        style="width: 100px"
                        size="small"
                      />
                      <span style="margin: 0 5px">-</span>
                      <el-time-select
                        v-model="cmd.time_end"
                        :min-time="cmd.time_start"
                        placeholder="结束时间"
                        start="00:00"
                        step="00:30"
                        end="23:30"
                        style="width: 100px"
                        size="small"
                      />
                    </template>
                  </div>
                </div>
                <el-button type="primary" size="small" @click="addCommand">
                  <el-icon><Plus /></el-icon>
                  添加指令
                </el-button>
              </div>
            </el-form-item>
          </el-collapse-item>
        </el-collapse>
      </el-form>

      <template #footer>
        <el-button @click="commandSetDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCommandSetSubmit" :loading="submitting">
          {{ isEditingCommandSet ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { commandSetApi, categoryApi, connectionApi, accessListApi } from '../api'

// 数据
const categories = ref([])
const commandSets = ref([])
const connections = ref([])
const accessLists = ref([])
const loading = ref(false)
const submitting = ref(false)
const advancedExpanded = ref([])

// 生成唯一 ID
const generateId = (name) => {
  const base = name
    ? name.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fa5]/g, '-').replace(/-+/g, '-').slice(0, 20)
    : ''
  const suffix = Date.now().toString(36).slice(-4)
  return base ? `${base}-${suffix}` : `item-${suffix}`
}

// 分类对话框
const categoryDialogVisible = ref(false)
const isEditingCategory = ref(false)
const editingCategoryId = ref('')
const categoryForm = ref({
  id: '',
  name: '',
  display_name: '',
  description: '',
  icon: '',
  order: 0,
  enabled: true,
  allow_user_switch: true,
  default_command_set: null,
  is_mutex: true,
})

// 指令集对话框
const commandSetDialogVisible = ref(false)
const isEditingCommandSet = ref(false)
const editingCommandSetId = ref('')
const commandSetForm = ref({
  id: '',
  name: '',
  prefix: '',
  category: '',
  description: '',
  is_public: false,
  strip_prefix: false,
  target_ws: '',
  priority: 0,
  enabled: true,
  user_access_list: null,
  group_access_list: null,
  is_default: false,
  commands: [],
})

// 计算属性：未分类的指令集
const uncategorizedSets = computed(() => {
  return commandSets.value.filter(cs => !cs.category)
})

// 计算属性：带指令集的分类列表（过滤掉无效分类）
const categoriesWithSets = computed(() => {
  return categories.value
    .filter(cat => cat.id) // 过滤掉 id 为空的分类
    .map(cat => ({
      ...cat,
      commandSets: commandSets.value.filter(cs => cs.category === cat.id),
    }))
    .sort((a, b) => a.order - b.order)
})

// 获取连接名称（通过 ID 查找）
const getConnectionName = (connId) => {
  if (!connId) return '-'
  const conn = connections.value.find(c => c.id === connId)
  return conn ? conn.name : connId
}

// 获取用户黑白名单
const userAccessLists = computed(() => accessLists.value.filter(al => al.type === 'user'))

// 获取群聊黑白名单
const groupAccessLists = computed(() => accessLists.value.filter(al => al.type === 'group'))

// 加载数据
const fetchData = async () => {
  loading.value = true
  try {
    const [csRes, catRes, connRes, alRes] = await Promise.all([
      commandSetApi.getAll(),
      categoryApi.getAll(),
      connectionApi.getAll(),
      accessListApi.getAll(),
    ])
    commandSets.value = csRes
    categories.value = catRes
    connections.value = connRes
    accessLists.value = alRes
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

// 分类相关方法
const showCreateCategoryDialog = () => {
  isEditingCategory.value = false
  categoryForm.value = {
    id: '',
    name: '',
    display_name: '',
    description: '',
    icon: '',
    order: 0,
    enabled: true,
    allow_user_switch: true,
    default_command_set: null,
    is_mutex: true,
  }
  categoryDialogVisible.value = true
}

const showEditCategoryDialog = (category) => {
  isEditingCategory.value = true
  editingCategoryId.value = category.id
  categoryForm.value = { ...category }
  categoryDialogVisible.value = true
}

const handleCategorySubmit = async () => {
  if (!categoryForm.value.display_name.trim()) {
    ElMessage.warning('请输入分类名称')
    return
  }

  submitting.value = true
  try {
    if (isEditingCategory.value) {
      await categoryApi.update(editingCategoryId.value, categoryForm.value)
      ElMessage.success('分类更新成功')
    } else {
      // 自动生成 id 和 name
      const id = generateId(categoryForm.value.display_name)
      const data = {
        ...categoryForm.value,
        id: id,
        name: id,
      }
      await categoryApi.create(data)
      ElMessage.success('分类创建成功')
    }
    categoryDialogVisible.value = false
    await fetchData()
  } catch (error) {
    ElMessage.error(isEditingCategory.value ? '更新失败' : '创建失败')
  } finally {
    submitting.value = false
  }
}

const handleDeleteCategory = async (category) => {
  if (category.commandSets.length > 0) {
    ElMessage.warning('请先删除或移动该分类下的指令集')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定要删除分类「${category.display_name}」吗？`,
      '确认删除',
      { type: 'warning' }
    )
    await categoryApi.delete(category.id)
    ElMessage.success('删除成功')
    await fetchData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 指令集相关方法
const showCreateCommandSetDialog = () => {
  isEditingCommandSet.value = false
  advancedExpanded.value = []
  commandSetForm.value = {
    id: '',
    name: '',
    prefix: '',
    category: '',
    description: '',
    is_public: false,
    strip_prefix: false,
    target_ws: '',
    priority: 0,
    enabled: true,
    user_access_list: null,
    group_access_list: null,
    is_default: false,
    commands: [],
  }
  commandSetDialogVisible.value = true
}

const showEditCommandSetDialog = (row) => {
  isEditingCommandSet.value = true
  editingCommandSetId.value = row.id
  advancedExpanded.value = ['advanced'] // 编辑时展开高级选项
  commandSetForm.value = {
    id: row.id,
    name: row.name,
    prefix: row.prefix || '',
    category: row.category || '',
    description: row.description || '',
    is_public: row.is_public || false,
    strip_prefix: row.strip_prefix || false,
    target_ws: row.target_ws || '',
    priority: row.priority || 0,
    enabled: row.enabled !== undefined ? row.enabled : true,
    user_access_list: row.user_access_list || null,
    group_access_list: row.group_access_list || null,
    is_default: row.is_default || false,
    commands: row.commands?.map(cmd => {
      // 转换时间限制格式
      const hasTime = !!cmd.time_restriction
      return {
        ...cmd,
        hasTimeRestriction: hasTime,
        time_start: hasTime ? cmd.time_restriction.start : '08:00',
        time_end: hasTime ? cmd.time_restriction.end : '22:00',
      }
    }) || [],
  }
  commandSetDialogVisible.value = true
}

const addCommand = () => {
  commandSetForm.value.commands.push({
    name: '',
    aliases: [],
    description: '',
    is_privileged: false,
    hasTimeRestriction: false,
    time_start: '08:00',
    time_end: '22:00',
  })
}

const toggleTimeRestriction = (cmd) => {
  if (!cmd.hasTimeRestriction) {
    cmd.time_start = '08:00'
    cmd.time_end = '22:00'
  }
}

const removeCommand = (index) => {
  commandSetForm.value.commands.splice(index, 1)
}

const handleCommandSetSubmit = async () => {
  if (!commandSetForm.value.name.trim()) {
    ElMessage.warning('请输入指令集名称')
    return
  }

  // 检测黑白名单冲突
  if (commandSetForm.value.user_access_list || commandSetForm.value.group_access_list) {
    try {
      const conflicts = await accessListApi.checkConflicts()
      if (conflicts.has_conflicts) {
        const conflictMsgs = conflicts.conflicts.map(c => 
          `${c.list1.name} 与 ${c.list2.name} 存在冲突项`
        ).join('\n')
        await ElMessageBox.confirm(
          `检测到黑白名单冲突：\n${conflictMsgs}\n\n确定继续保存吗？`,
          '冲突警告',
          { type: 'warning', confirmButtonText: '继续保存', cancelButtonText: '取消' }
        )
      }
    } catch (error) {
      if (error === 'cancel') return
      // 冲突检测失败不阻止保存
    }
  }

  // 转换指令时间限制格式
  const processedCommands = commandSetForm.value.commands.map(cmd => {
    const { hasTimeRestriction, time_start, time_end, ...rest } = cmd
    return {
      ...rest,
      time_restriction: hasTimeRestriction ? { start: time_start, end: time_end } : null,
    }
  })

  submitting.value = true
  try {
    const formData = {
      ...commandSetForm.value,
      commands: processedCommands,
    }
    
    if (isEditingCommandSet.value) {
      await commandSetApi.update(editingCommandSetId.value, formData)
      ElMessage.success('指令集更新成功')
    } else {
      // 自动生成 id
      const id = generateId(commandSetForm.value.name)
      const data = {
        ...formData,
        id: id,
        category: commandSetForm.value.category || null, // 空字符串转 null
      }
      await commandSetApi.create(data)
      ElMessage.success('指令集创建成功')
    }
    commandSetDialogVisible.value = false
    await fetchData()
  } catch (error) {
    console.error('Submit error:', error)
    ElMessage.error(isEditingCommandSet.value ? '更新失败' : '创建失败')
  } finally {
    submitting.value = false
  }
}

const handleDeleteCommandSet = async (row) => {
  if (!row.id) {
    ElMessage.error('该指令集 ID 无效，无法删除')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定要删除指令集「${row.name}」吗？`,
      '确认删除',
      { type: 'warning' }
    )
    await commandSetApi.delete(row.id)
    ElMessage.success('删除成功')
    await fetchData()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Delete error:', error)
      ElMessage.error('删除失败')
    }
  }
}

onMounted(fetchData)
</script>

<style scoped>
.action-bar {
  margin-bottom: 20px;
  display: flex;
  gap: 10px;
}

.category-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.category-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.category-title h3 {
  margin: 0;
}

.category-icon {
  font-size: 1.5em;
}

.category-actions {
  display: flex;
  gap: 5px;
}

.category-description {
  color: #666;
  margin: 0 0 15px 0;
  padding: 0 10px;
  font-size: 14px;
}

.commands-editor {
  width: 100%;
}

.command-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 15px;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 6px;
}

.command-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.command-options {
  display: flex;
  gap: 10px;
  align-items: center;
  padding-left: 10px;
}

:deep(.el-collapse) {
  border: none;
}

:deep(.el-collapse-item__header) {
  color: #409eff;
  font-size: 13px;
}

:deep(.el-collapse-item__wrap) {
  border: none;
}
</style>
