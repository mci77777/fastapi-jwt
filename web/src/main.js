/** 重置样式 */
import '@/styles/reset.css'
import 'uno.css'
import '@/styles/global.scss'

import { createApp } from 'vue'
import { setupRouter } from '@/router'
import { setupStore } from '@/store'
import App from './App.vue'
import { setupDirectives } from './directives'
import { useResize, initializeAuth } from '@/utils'
import i18n from '~/i18n'
import { setupRequestLogHooks } from '@/utils/http/requestLogHooks'

async function setupApp() {
  const app = createApp(App)

  setupStore(app)
  setupRequestLogHooks()

  // 初始化认证状态（恢复登录信息）
  await initializeAuth()

  await setupRouter(app)
  setupDirectives(app)
  app.use(useResize)
  app.use(i18n)
  app.mount('#app')
}

setupApp()
