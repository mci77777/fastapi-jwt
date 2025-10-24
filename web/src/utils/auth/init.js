import { getToken, getUserInfo, setUserInfo } from './token'
import { useUserStore } from '@/store'

/**
 * 应用初始化：恢复登录状态
 * 在应用启动时调用，检查 localStorage 中是否有有效的 token
 * 如果有，自动恢复用户登录状态
 */
export async function initializeAuth() {
  console.log('🔐 初始化认证状态...')

  try {
    const token = getToken()

    if (!token) {
      console.log('❌ 没有有效的 token，用户需要登录')
      return false
    }

    console.log('✅ 找到有效的 token，尝试恢复用户状态...')

    const userStore = useUserStore()

    // 1. 尝试从 localStorage 恢复用户信息
    const cachedUserInfo = getUserInfo()
    if (cachedUserInfo) {
      console.log('📦 从 localStorage 恢复用户信息:', cachedUserInfo.username)
      userStore.setUserInfo(cachedUserInfo)
      return true
    }

    // 2. 如果 localStorage 中没有用户信息，从后端获取
    console.log('📡 从后端获取用户信息...')
    const api = (await import('@/api')).default
    const userInfoRes = await api.getUserInfo()

    if (userInfoRes && userInfoRes.data) {
      console.log('✅ 成功获取用户信息:', userInfoRes.data.username)
      // 保存到 localStorage
      setUserInfo(userInfoRes.data)
      // 更新 Pinia store
      userStore.setUserInfo(userInfoRes.data)
      return true
    }

    console.warn('⚠️ 无法获取用户信息')
    return false
  } catch (error) {
    console.error('❌ 恢复用户状态失败:', error)
    // 即使恢复失败，也不要中断应用启动
    return false
  }
}
