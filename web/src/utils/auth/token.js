import { lStorage } from '@/utils'

const TOKEN_CODE = 'access_token'
const REFRESH_TOKEN_CODE = 'refresh_token'
const USER_INFO_CODE = 'user_info'

/**
 * 从 JWT token 中解码 payload（不验证签名）
 * @param {string} token - JWT token
 * @returns {object|null} - 解码后的 payload，或 null 如果解码失败
 */
export function decodeJWT(token) {
  try {
    if (!token || typeof token !== 'string') return null
    const parts = token.split('.')
    if (parts.length !== 3) return null

    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const padding = '='.repeat((4 - (base64.length % 4)) % 4)
    const payload = JSON.parse(atob(`${base64}${padding}`))
    return payload
  } catch (error) {
    console.error('JWT 解码失败:', error)
    return null
  }
}

/**
 * 检查 token 是否有效（未过期）
 * @param {string} token - JWT token
 * @returns {boolean} - token 是否有效
 */
function isTokenValid(token) {
  if (!token) return false

  const payload = decodeJWT(token)
  if (!payload || !payload.exp) return false

  // 当前时间（秒）
  const now = Math.floor(Date.now() / 1000)
  // token 是否已过期（留 10 秒缓冲）
  return payload.exp > now + 10
}

/**
 * 获取 token
 * @returns {string|null} - 有效的 token，或 null
 */
export function getToken() {
  try {
    const token = lStorage.get(TOKEN_CODE)

    // 如果 token 不存在或已过期，清除并返回 null
    if (!isTokenValid(token)) {
      if (token) {
        console.warn('⚠️ Token 已过期，清除本地存储')
        removeToken()
      }
      return null
    }

    return token
  } catch (error) {
    console.error('❌ 获取 token 时出错:', error)
    return null
  }
}

/**
 * 设置 token（自动计算过期时间）
 * @param {string} token - JWT token
 */
export function setToken(token) {
  if (!token) return

  const payload = decodeJWT(token)
  if (!payload || !payload.exp) {
    console.warn('无效的 JWT token，无法提取过期时间')
    // 即使无法提取过期时间，也保存 token（后端会验证）
    lStorage.set(TOKEN_CODE, token)
    return
  }

  // 计算 token 的过期时间（秒转毫秒）
  const expiresAt = payload.exp * 1000
  const now = Date.now()
  const expiresIn = Math.max(0, expiresAt - now)

  // 保存 token，设置过期时间
  lStorage.set(TOKEN_CODE, token, Math.ceil(expiresIn / 1000))

  console.log(`✅ Token 已保存，将在 ${Math.ceil(expiresIn / 1000)} 秒后过期`)
}

/**
 * 获取 refresh_token（不校验 exp，由 Supabase 负责管理其有效性）
 */
export function getRefreshToken() {
  return lStorage.get(REFRESH_TOKEN_CODE)
}

/**
 * 保存 refresh_token（建议存放在 *.local 环境下用于本地开发）
 */
export function setRefreshToken(token) {
  if (!token) return
  lStorage.set(REFRESH_TOKEN_CODE, token)
}

/**
 * 保存用户信息
 * @param {object} userInfo - 用户信息
 */
export function setUserInfo(userInfo) {
  if (!userInfo) return
  lStorage.set(USER_INFO_CODE, userInfo)
}

/**
 * 获取用户信息
 * @returns {object|null} - 用户信息，或 null
 */
export function getUserInfo() {
  return lStorage.get(USER_INFO_CODE)
}

/**
 * 移除 token 和用户信息
 */
export function removeToken() {
  lStorage.remove(TOKEN_CODE)
  lStorage.remove(REFRESH_TOKEN_CODE)
  lStorage.remove(USER_INFO_CODE)
}
