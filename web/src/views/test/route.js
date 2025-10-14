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
      name: 'Mock 用户测试',
      path: 'mock-user',
      component: () => import('./mock-user.vue'),
      meta: {
        title: 'Mock 用户测试',
        icon: 'mdi:account-cog',
        order: 1,
      },
    },
  ],
}
