/**
 * 教室情感识别（双维编码）前端 API
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 300000,
  withCredentials: true,
})

// ==================== 鉴权 ====================

export function login(username, password) {
  return api.post('/auth/login', { username, password })
}

export function logout() {
  return api.post('/auth/logout')
}

export function fetchMe() {
  return api.get('/auth/me')
}

// ==================== 双维识别历史 ====================

export function fetchHistory() {
  return api.get('/history')
}

export function deleteHistory(jobId) {
  return api.delete(`/history/${jobId}`)
}

export function deleteDualJob(jobId) {
  return api.delete(`/dual/jobs/${jobId}`)
}

// ==================== 教学情绪-行为双维编码 ====================

export function fetchDualCodebook() {
  return api.get('/dual/codebook')
}

export function fetchDualHistory() {
  return api.get('/dual/history')
}

export function uploadDualVideo(file) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/dual/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getDualJobResult(jobId) {
  return api.get(`/dual/jobs/${jobId}/result`)
}

export function getHistoryDualResult(jobId) {
  return getDualJobResult(jobId)
}

export function connectDualSSE(jobId, onMessage, onError) {
  const eventSource = new EventSource(`/api/dual/jobs/${jobId}/progress`, {
    withCredentials: true,
  })
  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      onMessage(data)
      if (data.status === 'done' || data.status === 'failed') {
        eventSource.close()
      }
    } catch (e) {
      console.error('Dual SSE parse error:', e)
    }
  }
  eventSource.onerror = (err) => {
    eventSource.close()
    if (onError) onError(err)
  }
  return eventSource
}

export function getDualOriginalVideoUrl(jobId) {
  return `/api/dual/jobs/${jobId}/original-video`
}

export function exportDualExcelWithEdits(jobId, payload) {
  return api.post(`/dual/jobs/${jobId}/export`, payload, {
    responseType: 'blob',
  })
}

export function getDualExportExcelUrl(jobId) {
  return `/api/dual/jobs/${jobId}/export`
}
