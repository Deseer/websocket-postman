import { createRouter, createWebHistory } from 'vue-router'

const routes = [
    {
        path: '/',
        redirect: '/dashboard',
    },
    {
        path: '/dashboard',
        name: 'Dashboard',
        component: () => import('./views/Dashboard.vue'),
        meta: { title: '仪表盘' },
    },
    {
        path: '/command-sets',
        name: 'CommandSets',
        component: () => import('./views/CommandSets.vue'),
        meta: { title: '指令集管理' },
    },
    {
        path: '/users',
        name: 'Users',
        component: () => import('./views/Users.vue'),
        meta: { title: '用户管理' },
    },
    {
        path: '/connections',
        name: 'Connections',
        component: () => import('./views/Connections.vue'),
        meta: { title: '连接管理' },
    },
    {
        path: '/settings',
        name: 'Settings',
        component: () => import('./views/Settings.vue'),
        meta: { title: '系统设置' },
    },
    {
        path: '/access-lists',
        name: 'AccessLists',
        component: () => import('./views/AccessLists.vue'),
        meta: { title: '黑白名单' },
    },
]

const router = createRouter({
    history: createWebHistory(),
    routes,
})

router.beforeEach((to, from, next) => {
    document.title = `${to.meta.title || 'WebSocket 指令分配器'} - 管理后台`
    next()
})

export default router
