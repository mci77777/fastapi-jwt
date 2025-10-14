const Layout = () => import('@/layout/index.vue')

export default {
  name: 'Catalog',
  path: '/catalog',
  component: Layout,
  meta: {
    title: '目录管理',
    icon: 'folder',
    order: 3,
  },
  children: [
    {
      path: '',
      name: 'CatalogIndex',
      component: () => import('./index.vue'),
      meta: {
        title: '目录管理',
        icon: 'folder',
        affix: false,
      },
    },
  ],
}
