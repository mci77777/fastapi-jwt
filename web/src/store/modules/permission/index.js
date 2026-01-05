import { defineStore } from 'pinia'
import { basicRoutes, vueModules } from '@/router/routes'
import Layout from '@/layout/index.vue'
import api from '@/api'

// * 后端路由相关函数
// 根据后端传来数据构建出前端路由

function buildRoutes(routes = []) {
  return routes.map((e) => {
    const route = {
      name: e.name,
      path: e.path,
      component: shallowRef(Layout),
      isHidden: e.is_hidden,
      redirect: e.redirect,
      meta: {
        title: e.name,
        icon: e.icon,
        order: e.order,
        keepAlive: e.keepalive,
      },
      children: [],
    }

    if (e.children && e.children.length > 0) {
      // 有子菜单
      route.children = e.children.map((e_child) => {
        const childRoute = {
          name: e_child.name,
          path: e_child.path,
          component: vueModules[`/src/views${e_child.component}/index.vue`],
          isHidden: e_child.is_hidden,
          meta: {
            title: e_child.name,
            icon: e_child.icon,
            order: e_child.order,
            keepAlive: e_child.keepalive,
          },
        }

        // Vue Router 4: 只在 alias 有效时才设置该字段，避免 alias=undefined 导致 addRoute 迭代失败
        if (typeof e_child.alias === 'string' && e_child.alias.trim()) {
          childRoute.alias = e_child.alias.trim()
        } else if (Array.isArray(e_child.alias) && e_child.alias.length) {
          childRoute.alias = e_child.alias.filter((v) => typeof v === 'string' && v.trim()).map((v) => v.trim())
        }

        return childRoute
      })
    } else {
      // 没有子菜单，创建一个默认的子路由
      route.children.push({
        name: `${e.name}Default`,
        path: '',
        component: vueModules[`/src/views${e.component}/index.vue`],
        isHidden: true,
        meta: {
          title: e.name,
          icon: e.icon,
          order: e.order,
          keepAlive: e.keepalive,
        },
      })
    }

    return route
  })
}

export const usePermissionStore = defineStore('permission', {
  state() {
    return {
      accessRoutes: [],
      accessApis: [],
    }
  },
  getters: {
    routes() {
      return basicRoutes.concat(this.accessRoutes)
    },
    menus() {
      return this.routes.filter((route) => route.name && !route.isHidden)
    },
    apis() {
      return this.accessApis
    },
  },
  actions: {
    async generateRoutes() {
      const res = await api.getUserMenu() // 调用接口获取后端传来的菜单路由
      this.accessRoutes = buildRoutes(res.data) // 处理成前端路由格式
      return this.accessRoutes
    },
    async getAccessApis() {
      const res = await api.getUserApi()
      this.accessApis = res.data
      return this.accessApis
    },
    resetPermission() {
      this.$reset()
    },
  },
})
