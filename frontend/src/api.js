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

// ==================== 识别历史 ====================

export function fetchHistory() {
  return api.get('/history')
}

export function getHistoryResult(jobId) {
  return api.get(`/history/${jobId}/result`)
}

// ==================== 任务 ====================

export function uploadVideo(file) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getJobResult(jobId) {
  return api.get(`/jobs/${jobId}/result`)
}

export function connectSSE(jobId, onMessage, onError) {
  const eventSource = new EventSource(`/api/jobs/${jobId}/progress`, {
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
      console.error('SSE parse error:', e)
    }
  }
  eventSource.onerror = (err) => {
    eventSource.close()
    if (onError) onError(err)
  }
  return eventSource
}

export function getSegmentVideoUrl(jobId, segmentIndex) {
  return `/api/jobs/${jobId}/video/${segmentIndex}`
}

export function getOriginalVideoUrl(jobId) {
  return `/api/jobs/${jobId}/original-video`
}

export function getExportExcelUrl(jobId) {
  return `/api/jobs/${jobId}/export`
}

/** 用前端编辑后的情感数据导出 Excel */
export function exportExcelWithEdits(jobId, payload) {
  return api.post(`/jobs/${jobId}/export`, payload, {
    responseType: 'blob',
  })
}

// ==================== 实时识别 WebSocket ====================

/**
 * 创建实时识别 WebSocket 连接
 * @param {Object} handlers - { onMessage, onOpen, onClose, onError }
 * @returns {WebSocket}
 */
export function createRealtimeSocket(handlers = {}) {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const ws = new WebSocket(`${protocol}//${location.host}/api/ws/realtime`)

  ws.onopen = (event) => {
    console.log('[Realtime WS] 连接已建立')
    handlers.onOpen?.(event)
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      handlers.onMessage?.(data)
    } catch (e) {
      console.error('[Realtime WS] 消息解析失败:', e)
    }
  }

  ws.onclose = (event) => {
    console.log('[Realtime WS] 连接已关闭', event.code, event.reason)
    handlers.onClose?.(event)
  }

  ws.onerror = (event) => {
    console.error('[Realtime WS] 连接错误', event)
    handlers.onError?.(event)
  }

  return ws
}

/**
 * 获取实时识别结果的下载链接
 * @param {string} jobId
 * @returns {string}
 */
export function getRealtimeExportUrl(jobId) {
  return `/api/jobs/${jobId}/export`
}
