import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('admin_token')
    }
    return Promise.reject(err)
  }
)

export const fetchModels = () => api.get('/models').then(r => r.data)

export const fetchModelOptions = (model) =>
  api.get('/model-options', { params: { model } }).then(r => r.data)

export const fetchSearch = (params) => api.get('/search', { params }).then(r => r.data)

export const fetchStats = (params) => api.get('/stats', { params }).then(r => r.data)

export const fetchLot = (id) => api.get(`/lot/${id}`).then(r => r.data)

export const fetchAdminStatus = () => api.get('/admin/status').then(r => r.data)

export const triggerSync = () => api.post('/admin/sync').then(r => r.data)

export const triggerMigrate = () => api.post('/admin/migrate').then(r => r.data)

export const triggerRelink = () => api.post('/admin/relink').then(r => r.data)

export const triggerRenormalize = () => api.post('/admin/renormalize').then(r => r.data)

export const triggerFreshRescrape = (force = false) => api.post(`/admin/fresh-rescrape?force=${force}`).then(r => r.data)

export const triggerResumeRescrape = () => api.post('/admin/resume-rescrape').then(r => r.data)

export const login = (password) =>
  api.post('/auth/login', { password }).then(r => {
    localStorage.setItem('admin_token', r.data.access_token)
    return r.data
  })

export const fetchExchangeRate = () => api.get('/exchange-rate').then(r => r.data)

export const fetchWatchlist = () => api.get('/watchlist').then(r => r.data)

export const fetchLbcSearch = (query, filters = {}) =>
  api.get('/watchlist/lbc-search', { params: { query, ...filters } }).then(r => r.data)

export const fetchArchive = () => api.get('/archive').then(r => r.data)

export const addToArchive = (data) => api.post('/archive', data).then(r => r.data)

export const updateArchiveEntry = (id, data) => api.patch(`/archive/${id}`, data).then(r => r.data)

export const deleteArchiveEntry = (id) => api.delete(`/archive/${id}`)

export default api
