const Layout = () => import('@/layout/index.vue')

export default {
  name: 'AI模型管理',
  path: '/ai',
  component: Layout,
  meta: {
    title: 'AI模型管理',
    icon: 'mdi:robot-outline',
    order: 5,
  },
  children: [
    {
      name: 'AiModelDashboard',
      path: 'model-suite/dashboard',
      component: () => import('./model-suite/dashboard/index.vue'),
      meta: {
        title: '模型仪表盘',
        icon: 'mdi:view-dashboard-outline',
        keepAlive: false, // 禁用缓存以避免DOM引用错误
      },
    },
    {
      name: 'AiModelCatalog',
      path: 'model-suite/catalog',
      component: () => import('./model-suite/catalog/index.vue'),
      meta: {
        title: '模型目录',
        icon: 'mdi:database-outline',
        keepAlive: false, // 禁用缓存以避免DOM引用错误
      },
    },
    {
      name: 'AiModelMapping',
      path: 'model-suite/mapping',
      component: () => import('./model-suite/mapping/index.vue'),
      meta: {
        title: '模型映射',
        icon: 'mdi:map-marker-path',
        keepAlive: false, // 禁用缓存以避免DOM引用错误
      },
    },
    {
      name: 'AiJwtSimulation',
      path: 'model-suite/jwt',
      component: () => import('./model-suite/jwt/index.vue'),
      meta: {
        title: 'JWT测试',
        icon: 'mdi:test-tube',
        keepAlive: false, // 禁用缓存以避免DOM引用错误
      },
    },
  ],
}
