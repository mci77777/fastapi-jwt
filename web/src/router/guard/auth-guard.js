import { getToken, isNullOrWhitespace } from '@/utils'
import { usePermissionStore } from '@/store'
import { addDynamicRoutes } from '@/router'

const WHITE_LIST = ['/login', '/404']
export function createAuthGuard(router) {
  router.beforeEach(async (to) => {
    const token = getToken()

    /** 没有token的情况 */
    if (isNullOrWhitespace(token)) {
      if (WHITE_LIST.includes(to.path)) return true
      // 修复：使用绝对路径 '/login' 而不是相对路径 'login'
      // 如果访问根路径 '/'，不保存 redirect 参数（避免循环重定向）
      if (to.path === '/') {
        return { path: '/login' }
      }
      return { path: '/login', query: { ...to.query, redirect: to.path } }
    }

    /** 有token的情况 */
    // 检查动态路由是否已加载
    const permissionStore = usePermissionStore()
    if (permissionStore.accessRoutes.length === 0) {
      // 动态路由未加载，先加载
      await addDynamicRoutes()
      // 重新导航到目标路由
      return { ...to, replace: true }
    }

    if (to.path === '/login') return { path: '/dashboard' }
    return true
  })
}
