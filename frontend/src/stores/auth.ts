import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api'
import type { LoginRequest } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  // State
  const token = ref<string>(localStorage.getItem('token') || '')
  const username = ref<string>('')
  const loading = ref(false)
  const error = ref<string>('')

  // Getters
  const isLoggedIn = computed(() => !!token.value)

  // Actions
  const login = async (credentials: LoginRequest) => {
    loading.value = true
    error.value = ''
    
    try {
      const response = await authApi.login(credentials)
      token.value = response.data.access_token
      username.value = credentials.username
      
      // 保存 token 到 localStorage
      localStorage.setItem('token', token.value)
      
      return true
    } catch (err: any) {
      error.value = err.response?.data?.detail || '登录失败'
      return false
    } finally {
      loading.value = false
    }
  }

  const logout = () => {
    token.value = ''
    username.value = ''
    localStorage.removeItem('token')
  }

  const verifyToken = async () => {
    if (!token.value) return false
    
    try {
      const response = await authApi.verify()
      username.value = response.data.username
      return true
    } catch {
      // Token 无效，清除状态
      logout()
      return false
    }
  }

  return {
    token,
    username,
    loading,
    error,
    isLoggedIn,
    login,
    logout,
    verifyToken
  }
})
