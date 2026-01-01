const Layout = () => import('@/layout/index.vue')

export default {
  name: '开发工具',
  path: '/test',
  component: Layout,
  order: 999,
  isHidden: false,
  meta: {
    title: '开发工具',
    icon: 'mdi:tools',
    order: 999,
  },
  children: [
    {
      name: '真实用户 SSE 测试',
      path: 'real-user-sse',
      component: () => import('./real-user-sse.vue'),
      meta: {
        title: '真实用户 SSE 测试',
        icon: 'mdi:account-cog',
        order: 1,
      },
    },
  ],
}
