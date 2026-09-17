import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({ baseURL: '/', timeout: 20000 })

http.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    ElMessage.error(typeof msg === 'string' ? msg : '请求失败')
    return Promise.reject(err)
  }
)

export default http

export const dashboardApi = {
  get: () => http.get('/api/dashboard').then((r) => r.data),
}

export const collectionApi = {
  list: (params) => http.get('/api/collections', { params }).then((r) => r.data),
  meta: () => http.get('/api/collections/meta').then((r) => r.data),
  get: (id) => http.get(`/api/collections/${id}`).then((r) => r.data),
  create: (data) => http.post('/api/collections', data).then((r) => r.data),
  update: (id, data) => http.put(`/api/collections/${id}`, data).then((r) => r.data),
  remove: (id) => http.delete(`/api/collections/${id}`).then((r) => r.data),
  move: (id, data) =>
    http.post(`/api/collections/${id}/movements`, data).then((r) => r.data),
  exhibitionExceptions: (id, params) =>
    http.get(`/api/collections/${id}/exhibition-exceptions`, { params }).then((r) => r.data),
}

export const movementApi = {
  list: (params) => http.get('/api/movements', { params }).then((r) => r.data),
}

export const locationApi = {
  list: (params) => http.get('/api/locations', { params }).then((r) => r.data),
  create: (data) => http.post('/api/locations', data).then((r) => r.data),
  update: (id, data) => http.put(`/api/locations/${id}`, data).then((r) => r.data),
  remove: (id) => http.delete(`/api/locations/${id}`).then((r) => r.data),
  addReading: (id, data) =>
    http.post(`/api/locations/${id}/readings`, data).then((r) => r.data),
}

export const exhibitionApi = {
  list: (params) => http.get('/api/exhibitions', { params }).then((r) => r.data),
  get: (id) => http.get(`/api/exhibitions/${id}`).then((r) => r.data),
  create: (data) => http.post('/api/exhibitions', data).then((r) => r.data),
  update: (id, data) => http.put(`/api/exhibitions/${id}`, data).then((r) => r.data),
  freeze: (id, operator) =>
    http.post(`/api/exhibitions/${id}/freeze`, { operator }).then((r) => r.data),
  unfreeze: (id) => http.post(`/api/exhibitions/${id}/unfreeze`).then((r) => r.data),
  addItem: (id, data) =>
    http.post(`/api/exhibitions/${id}/items`, data).then((r) => r.data),
  updateItem: (id, itemId, data) =>
    http.put(`/api/exhibitions/${id}/items/${itemId}`, data).then((r) => r.data),
  removeItem: (id, itemId) =>
    http.delete(`/api/exhibitions/${id}/items/${itemId}`).then((r) => r.data),
  mount: (id, itemId, data) =>
    http.post(`/api/exhibitions/${id}/items/${itemId}/mount`, data).then((r) => r.data),
  dismount: (id, itemId, data) =>
    http.post(`/api/exhibitions/${id}/items/${itemId}/dismount`, data).then((r) => r.data),
  addException: (id, itemId, data) =>
    http.post(`/api/exhibitions/${id}/items/${itemId}/exceptions`, data).then((r) => r.data),
  resolveException: (exceptionId, data) =>
    http.post(`/api/exhibitions/exceptions/${exceptionId}/resolve`, data).then((r) => r.data),
  createChangeOrder: (id, data) =>
    http.post(`/api/exhibitions/${id}/change-orders`, data).then((r) => r.data),
  approveChangeOrder: (orderId, data) =>
    http.post(`/api/exhibitions/change-orders/${orderId}/approve`, data).then((r) => r.data),
  rejectChangeOrder: (orderId, data) =>
    http.post(`/api/exhibitions/change-orders/${orderId}/reject`, data).then((r) => r.data),
  executeChangeOrder: (orderId, data) =>
    http.post(`/api/exhibitions/change-orders/${orderId}/execute`, data).then((r) => r.data),
}

export const restorationApi = {
  list: (params) => http.get('/api/restorations', { params }).then((r) => r.data),
  create: (data) => http.post('/api/restorations', data).then((r) => r.data),
  addTimeline: (id, data) =>
    http.post(`/api/restorations/${id}/timeline`, data).then((r) => r.data),
  complete: (id, data, return_location_id) =>
    http
      .post(`/api/restorations/${id}/complete`, data, {
        params: return_location_id ? { return_location_id } : {},
      })
      .then((r) => r.data),
}

export const loanApi = {
  list: (params) => http.get('/api/loans', { params }).then((r) => r.data),
  create: (data) => http.post('/api/loans', data).then((r) => r.data),
  return: (id, data) => http.post(`/api/loans/${id}/return`, data).then((r) => r.data),
}

export const envApi = {
  readings: (location_id, hours = 72) =>
    http.get('/api/environment/readings', { params: { location_id, hours } }).then((r) => r.data),
  alerts: (params) => http.get('/api/environment/alerts', { params }).then((r) => r.data),
  ack: (id, by = '管理员') =>
    http.post(`/api/environment/alerts/${id}/ack`, null, { params: { by } }).then((r) => r.data),
  simulate: (data) => http.post('/api/environment/simulate', data).then((r) => r.data),
}
