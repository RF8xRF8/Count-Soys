import axios from 'axios'

const request = axios.create({ baseURL: '/api', timeout: 30000 })
request.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
request.interceptors.response.use(response => {
  if (response.data?.code && response.data.code !== 0) return Promise.reject(new Error(response.data.message))
  return response.data.data
}, async error => {
  const original = error.config
  if (error.response?.status === 401 && !original?._retried) {
    original._retried = true
    const refreshToken = localStorage.getItem('refresh_token')
    if (refreshToken) {
      try {
        const result = await axios.post('/api/auth/refresh', { refresh_token: refreshToken })
        localStorage.setItem('access_token', result.data.data.access_token)
        original.headers.Authorization = `Bearer ${result.data.data.access_token}`
        return request(original)
      } catch { localStorage.clear() }
    }
  }
  return Promise.reject(error)
})
export default request
