import axios from 'axios'

const api = axios.create({
    baseURL: '/api',
    timeout: 10000,
})

// 请求拦截器
api.interceptors.request.use(
    config => {
        return config
    },
    error => {
        return Promise.reject(error)
    }
)

// 响应拦截器
api.interceptors.response.use(
    response => {
        return response.data
    },
    error => {
        console.error('API Error:', error)
        return Promise.reject(error)
    }
)

// 分类 API
export const categoryApi = {
    getAll: () => api.get('/categories'),
    create: data => api.post('/categories', data),
    update: (id, data) => api.put(`/categories/${id}`, data),
    delete: id => api.delete(`/categories/${id}`),
}

// 指令集 API
export const commandSetApi = {
    getAll: () => api.get('/command-sets'),
    get: id => api.get(`/command-sets/${id}`),
    create: data => api.post('/command-sets', data),
    update: (id, data) => api.put(`/command-sets/${id}`, data),
    delete: id => api.delete(`/command-sets/${id}`),
    getMutualExclusiveGroups: () => api.get('/command-sets/groups/mutual-exclusive'),
}

// 用户 API
export const userApi = {
    getAll: (skip = 0, limit = 100) => api.get('/users', { params: { skip, limit } }),
    get: id => api.get(`/users/${id}`),
    update: (id, data) => api.put(`/users/${id}`, data),
    allowGroup: (userId, group) => api.post(`/users/${userId}/allow-group/${group}`),
    denyGroup: (userId, group) => api.delete(`/users/${userId}/allow-group/${group}`),
    setStyle: (userId, group, styleId) => api.post(`/users/${userId}/style/${group}/${styleId}`),
}

// 连接 API
export const connectionApi = {
    getAll: () => api.get('/connections'),
    create: data => api.post('/connections', data),
    update: (id, data) => api.put(`/connections/${id}`, data),
    delete: id => api.delete(`/connections/${id}`),
    connect: id => api.post(`/connections/${id}/connect`),
    disconnect: id => api.post(`/connections/${id}/disconnect`),
}

// 监控 API
export const monitorApi = {
    getStats: () => api.get('/monitor/stats'),
    getLogs: (lines = 200) => api.get(`/monitor/system-logs?lines=${lines}`),
    getConnectionStatus: () => api.get('/monitor/connections'),
}

// 配置 API
export const configApi = {
    get: () => api.get('/config'),
    update: data => api.put('/config', data),
}

// 黑白名单 API
export const accessListApi = {
    getAll: () => api.get('/access-lists'),
    get: id => api.get(`/access-lists/${id}`),
    create: data => api.post('/access-lists', data),
    update: (id, data) => api.put(`/access-lists/${id}`, data),
    delete: id => api.delete(`/access-lists/${id}`),
    checkConflicts: () => api.get('/access-lists/conflicts'),
}

export default api
