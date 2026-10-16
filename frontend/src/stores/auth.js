import { defineStore } from 'pinia'
import request from '../api'

export const useAuthStore = defineStore('auth', {
  state: () => ({ user: JSON.parse(localStorage.getItem('user') || 'null'), accessToken: localStorage.getItem('access_token'), refreshToken: localStorage.getItem('refresh_token') }),
  getters: { isLoggedIn: state => Boolean(state.accessToken), isAdmin: state => state.user?.role === 'admin' },
  actions: {
    async login(username, password) {
      const result = await request.post('/auth/login', { username, password })
      this.accessToken = result.access_token; this.refreshToken = result.refresh_token; this.user = result.user
      localStorage.setItem('access_token', this.accessToken); localStorage.setItem('refresh_token', this.refreshToken); localStorage.setItem('user', JSON.stringify(this.user))
    },
    clear() { this.user = null; this.accessToken = null; this.refreshToken = null; localStorage.clear() },
    async logout() { try { await request.post('/auth/logout') } finally { this.clear() } }
  }
})
