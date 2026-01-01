<template>
  <AppPage :show-footer="true" bg-cover :style="{ backgroundImage: `url(${bgImg})` }">
    <div
      style="transform: translateY(25px)"
      class="m-auto max-w-1500 min-w-345 f-c-c rounded-10 bg-white bg-opacity-60 p-15 card-shadow"
      dark:bg-dark
    >
      <div hidden w-380 px-20 py-35 md:block>
        <icon-custom-front-page pt-10 text-300 color-primary></icon-custom-front-page>
      </div>

      <div w-320 flex-col px-20 py-35>
        <h5 f-c-c text-24 font-normal color="#6a6a6a">
          <icon-custom-logo mr-10 text-50 color-primary />{{ $t('app_name') }}
        </h5>
        <div mt-30>
          <n-input
            v-model:value="loginInfo.email"
            autofocus
            class="h-50 items-center pl-10 text-16"
            placeholder="email@example.com"
            :maxlength="120"
          />
        </div>
        <div mt-30>
          <n-input
            v-model:value="loginInfo.password"
            class="h-50 items-center pl-10 text-16"
            type="password"
            show-password-on="mousedown"
            placeholder="输入密码"
            :maxlength="200"
            @keypress.enter="handleLogin"
          />
        </div>

        <div mt-20>
          <n-button
            h-50
            w-full
            rounded-5
            text-16
            type="primary"
            :loading="loading"
            @click="handleLogin"
          >
            {{ $t('views.login.text_login') }}
          </n-button>
        </div>
      </div>
    </div>
  </AppPage>
</template>

<script setup>
import { lStorage, setRefreshToken, setToken, setUserInfo } from '@/utils'
import bgImg from '@/assets/images/login_bg.webp'
import api from '@/api'
import { addDynamicRoutes } from '@/router'
import { useUserStore } from '@/store'
import { useI18n } from 'vue-i18n'

const router = useRouter()
const { query } = useRoute()
const { t } = useI18n({ useScope: 'global' })
const userStore = useUserStore()

const loginInfo = ref({
  email: '',
  password: '',
})

initLoginInfo()

function initLoginInfo() {
  const localLoginInfo = lStorage.get('loginInfo')
  if (localLoginInfo) {
    loginInfo.value.email = localLoginInfo.email || localLoginInfo.username || ''
    loginInfo.value.password = localLoginInfo.password || ''
  }
}

const loading = ref(false)
async function handleLogin() {
  const { email, password } = loginInfo.value
  if (!email || !password) {
    $message.warning(t('views.login.message_input_username_password'))
    return
  }
  try {
    loading.value = true
    $message.loading(t('views.login.message_verifying'))
    const res = await api.login({ email, password: password.toString() })
    $message.success(t('views.login.message_login_success'))

    // 1. 保存 token（包括过期时间）
    setToken(res.data.access_token)
    if (res.data.refresh_token) setRefreshToken(res.data.refresh_token)

    // 2. 获取用户信息
    const userInfoRes = await api.getUserInfo()
    if (userInfoRes && userInfoRes.data) {
      // 3. 保存用户信息到 localStorage
      setUserInfo(userInfoRes.data)
      // 4. 更新 Pinia store
      userStore.setUserInfo(userInfoRes.data)
    }

    // 5. 加载动态路由
    await addDynamicRoutes()

    // 6. 跳转到目标页面
    if (query.redirect) {
      const path = query.redirect
      Reflect.deleteProperty(query, 'redirect')
      router.push({ path, query })
    } else {
      router.push('/dashboard')
    }
  } catch (e) {
    console.error('login error', e.error)
  }
  loading.value = false
}
</script>
