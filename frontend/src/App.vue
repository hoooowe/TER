<template>
  <div class="app">
    <header class="app-header">
      <h1>情感识别系统</h1>
      <nav v-if="user" class="mode-tabs">
        <button
          :class="['tab', { active: mode === 'upload' }]"
          @click="switchMode('upload')"
        >
          📹 视频分析
        </button>
        <button
          :class="['tab', { active: mode === 'history' }]"
          @click="switchMode('history')"
        >
          🕘 识别历史
        </button>
        <button
          :class="['tab', { active: mode === 'realtime' }]"
          @click="switchMode('realtime')"
        >
          📷 实时识别
        </button>
      </nav>
      <div v-if="user" class="user-area">
        <span class="user-name">{{ user.username }}</span>
        <button class="logout-btn" @click="onLogout">退出</button>
      </div>
    </header>

    <main class="app-main">
      <LoginView
        v-if="!user && authChecked"
        :hint="loginHint"
        @success="onLoginSuccess"
      />

      <div v-else-if="!user && !authChecked" class="auth-loading">检查登录状态…</div>

      <!-- 视频分析模式：左右分栏 -->
      <template v-else-if="mode === 'upload'">
        <div class="workspace">
          <!-- 左侧：上传 / 进度 / 视频 -->
          <section class="panel panel-left">
            <div v-if="!jobId" class="left-placeholder">
              <VideoUpload
                :disabled="processing"
                @upload-start="onUploadStart"
                @upload-success="onUploadSuccess"
                @upload-error="onUploadError"
              />
            </div>

            <div v-else class="left-stack">
              <ProgressPanel
                :visible="processing"
                :progress="progress"
                :message="progressMessage"
                :status="jobStatus"
              />

              <div v-if="error" class="error-banner">{{ error }}</div>

              <VideoPlayer
                :job-id="jobId"
                :segments="segments"
                :label-mode="labelMode"
              />
            </div>
          </section>

          <!-- 右侧：识别结果 / 编辑 / 导出 -->
          <section class="panel panel-right">
            <div v-if="error && !jobId" class="error-banner">{{ error }}</div>

            <div v-if="!segments.length && processing" class="right-placeholder processing">
              <div class="placeholder-icon">⏳</div>
              <p class="placeholder-title">正在识别情感…</p>
              <p class="placeholder-hint">{{ progressMessage || '每识别完一段会立即显示在此处' }}</p>
              <div class="mini-progress">
                <div class="mini-progress-fill" :style="{ width: (progress * 100) + '%' }"></div>
              </div>
            </div>

            <div v-else-if="!segments.length" class="right-placeholder">
              <div class="placeholder-icon">🎯</div>
              <p class="placeholder-title">识别结果将显示在这里</p>
              <p class="placeholder-hint">上传视频后，片段结果会逐条出现；可编辑情感与文本，导出使用编辑后的内容</p>
            </div>

            <template v-else>
              <div class="result-toolbar">
                <div class="mode-toggle">
                  <span class="mode-label">标签体系</span>
                  <span class="mode-badge">emotion2vec 通用情感 (9类)</span>
                  <span v-if="fromHistory" class="history-badge">历史记录</span>
                  <span v-if="processing" class="live-badge">
                    识别中 {{ liveInfo.done }}{{ liveInfo.total ? `/${liveInfo.total}` : '' }} 段
                  </span>
                </div>

                <div class="export-actions">
                  <button
                    class="export-btn csv"
                    :disabled="exporting"
                    @click="onExportCsv"
                  >
                    {{ exporting === 'csv' ? '导出中…' : '导出 CSV' }}
                  </button>
                  <button
                    class="export-btn excel"
                    :disabled="exporting"
                    @click="onExportExcel"
                  >
                    {{ exporting === 'excel' ? '导出中…' : '导出 Excel' }}
                  </button>
                </div>
              </div>

              <div v-if="processing" class="live-progress">
                <div class="live-progress-bar">
                  <div class="live-progress-fill" :style="{ width: (progress * 100) + '%' }"></div>
                </div>
                <span class="live-progress-text">{{ progressMessage || '处理中…' }}</span>
              </div>

              <p v-if="exportHint" class="export-hint">{{ exportHint }}</p>
              <p v-else-if="processing" class="export-hint">已出片段可先预览/编辑；全部完成后结果会自动对齐</p>

              <EmotionTimeline
                :segments="segments"
                :total-duration="result?.total_duration || 0"
                :label-mode="labelMode"
              />

              <ResultTable
                :segments="segments"
                :label-mode="labelMode"
                @update-label="onUpdateLabel"
                @update-text="onUpdateText"
              />
            </template>
          </section>
        </div>
      </template>

      <!-- 识别历史 -->
      <template v-else-if="mode === 'history'">
        <div class="history-layout">
          <HistoryPanel
            ref="historyPanelRef"
            :active-job-id="jobId"
            @select="onSelectHistory"
          />
          <section class="panel panel-right history-result">
            <div v-if="!segments.length && !result" class="right-placeholder">
              <div class="placeholder-icon">🕘</div>
              <p class="placeholder-title">选择左侧历史记录</p>
              <p class="placeholder-hint">点击某条识别历史后，可在此查看时间轴、编辑文本/情感并导出；处理中的任务会实时增量显示</p>
            </div>
            <template v-else-if="segments.length || result">
              <div class="result-toolbar">
                <div class="mode-toggle">
                  <span class="mode-label">{{ result?.video_name || result?.job_id || jobId }}</span>
                  <span class="mode-badge">emotion2vec 通用情感 (9类)</span>
                  <span class="history-badge">历史记录</span>
                  <span v-if="processing" class="live-badge">
                    识别中 {{ liveInfo.done }}{{ liveInfo.total ? `/${liveInfo.total}` : '' }} 段
                  </span>
                </div>
                <div class="export-actions">
                  <button
                    class="export-btn csv"
                    :disabled="exporting || !segments.length"
                    @click="onExportCsv"
                  >
                    {{ exporting === 'csv' ? '导出中…' : '导出 CSV' }}
                  </button>
                  <button
                    class="export-btn excel"
                    :disabled="exporting || !segments.length"
                    @click="onExportExcel"
                  >
                    {{ exporting === 'excel' ? '导出中…' : '导出 Excel' }}
                  </button>
                  <button class="export-btn open" @click="openInUpload">在分析页打开</button>
                </div>
              </div>
              <div v-if="processing" class="live-progress">
                <div class="live-progress-bar">
                  <div class="live-progress-fill" :style="{ width: (progress * 100) + '%' }"></div>
                </div>
                <span class="live-progress-text">{{ progressMessage || '处理中…' }}</span>
              </div>
              <p v-if="exportHint" class="export-hint">{{ exportHint }}</p>
              <template v-if="segments.length">
                <EmotionTimeline
                  :segments="segments"
                  :total-duration="result?.total_duration || 0"
                  :label-mode="labelMode"
                />
                <ResultTable
                  :segments="segments"
                  :label-mode="labelMode"
                  @update-label="onUpdateLabel"
                  @update-text="onUpdateText"
                />
              </template>
            </template>
          </section>
        </div>
      </template>

      <!-- 实时识别模式 -->
      <template v-else-if="mode === 'realtime'">
        <RealtimeRecognition />
      </template>
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import VideoUpload from './components/VideoUpload.vue'
import VideoPlayer from './components/VideoPlayer.vue'
import ProgressPanel from './components/ProgressPanel.vue'
import EmotionTimeline from './components/EmotionTimeline.vue'
import ResultTable from './components/ResultTable.vue'
import RealtimeRecognition from './components/RealtimeRecognition.vue'
import LoginView from './components/LoginView.vue'
import HistoryPanel from './components/HistoryPanel.vue'
import {
  connectSSE,
  getJobResult,
  getHistoryResult,
  exportExcelWithEdits,
  fetchMe,
  logout,
} from './api.js'
import { applyLabelEdit, applyTextEdit, isLabelEdited, isTextEdited, ACTIVE_LABEL_MODE } from './emotionConfig.js'
import { exportCsv, exportExcel } from './exportUtils.js'

const mode = ref('upload') // 'upload' | 'history' | 'realtime'
const user = ref(null)
const authChecked = ref(false)
const loginHint = ref('')

const processing = ref(false)
const progress = ref(0)
const progressMessage = ref('')
const jobStatus = ref('')
const error = ref('')
const result = ref(null)
const jobId = ref('')
const fromHistory = ref(false)
const historyPanelRef = ref(null)
// 暂时只启用通用 emotion2vec 9 类
const labelMode = ref(ACTIVE_LABEL_MODE)
const segments = ref([])
const exporting = ref('')
const exportHint = ref('')
const liveInfo = ref({ done: 0, total: 0 })

function switchMode(newMode) {
  mode.value = newMode
}

function mapOneSegment(seg) {
  return {
    ...seg,
    original_label: seg.label,
    original_label_name_cn: seg.label_name_cn,
    original_label_name: seg.label_name,
    original_emotion2vec_label: seg.emotion2vec_label,
    original_emotion2vec_label_name: seg.emotion2vec_label_name,
    original_text: seg.text,
  }
}

function mapSegments(rawSegments) {
  return (rawSegments || []).map(mapOneSegment)
}

function preserveEdits(prev, next) {
  if (!prev) return next
  return {
    ...next,
    text: isTextEdited(prev) ? prev.text : next.text,
    emotion2vec_label: isLabelEdited(prev, 'e2v') ? prev.emotion2vec_label : next.emotion2vec_label,
    emotion2vec_label_name: isLabelEdited(prev, 'e2v')
      ? prev.emotion2vec_label_name
      : next.emotion2vec_label_name,
    label: isLabelEdited(prev, 'teacher') ? prev.label : next.label,
    label_name_cn: isLabelEdited(prev, 'teacher') ? prev.label_name_cn : next.label_name_cn,
  }
}

function upsertSegmentsFromServer(rawSegments) {
  const prevMap = new Map(segments.value.map((s) => [s.index, s]))
  const next = mapSegments(rawSegments).map((seg) => preserveEdits(prevMap.get(seg.index), seg))
  next.sort((a, b) => a.index - b.index)
  segments.value = next
  syncResultShell()
}

function syncResultShell() {
  if (!segments.value.length && !jobId.value) {
    result.value = null
    return
  }
  const base = result.value || {}
  result.value = {
    job_id: jobId.value || base.job_id || '',
    video_name: base.video_name || '',
    total_duration: base.total_duration || 0,
    segments: segments.value,
    complete: !processing.value,
  }
}

function applyLivePayload(data) {
  progress.value = data.progress ?? progress.value
  progressMessage.value = data.message || progressMessage.value
  jobStatus.value = data.status || jobStatus.value

  if (data.video_name && result.value) {
    result.value = { ...result.value, video_name: data.video_name }
  } else if (data.video_name && !result.value) {
    result.value = {
      job_id: jobId.value || data.job_id || '',
      video_name: data.video_name,
      total_duration: data.total_duration || 0,
      segments: [],
      complete: false,
    }
  } else if (!result.value && jobId.value) {
    result.value = {
      job_id: jobId.value,
      video_name: '',
      total_duration: data.total_duration || 0,
      segments: [],
      complete: false,
    }
  }

  if (data.total_duration && result.value) {
    result.value = { ...result.value, total_duration: data.total_duration }
  }

  if (Array.isArray(data.segments)) {
    upsertSegmentsFromServer(data.segments)
  }
  if (data.segment) {
    const prevMap = new Map(segments.value.map((s) => [s.index, s]))
    const mapped = preserveEdits(prevMap.get(data.segment.index), mapOneSegment(data.segment))
    const arr = segments.value.filter((s) => s.index !== mapped.index)
    arr.push(mapped)
    arr.sort((a, b) => a.index - b.index)
    segments.value = arr
    syncResultShell()
  }

  liveInfo.value = {
    done: data.segments_done ?? segments.value.length,
    total: data.segments_total ?? liveInfo.value.total,
  }
}

function applyResultData(data, { keepProcessing = false } = {}) {
  const prevMap = new Map(segments.value.map((s) => [s.index, s]))
  const mapped = mapSegments(data.segments).map((seg) => preserveEdits(prevMap.get(seg.index), seg))
  result.value = { ...data, segments: mapped }
  segments.value = mapped
  if (!keepProcessing) {
    processing.value = false
    if (data.complete !== false) {
      liveInfo.value = { done: mapped.length, total: mapped.length }
    }
  } else if (Array.isArray(data.segments)) {
    liveInfo.value = {
      done: data.segments.length,
      total: liveInfo.value.total || data.segments.length,
    }
  }
  error.value = ''
  if (!keepProcessing) exportHint.value = ''
}

function onUploadStart() {
  error.value = ''
  result.value = null
  jobId.value = ''
  segments.value = []
  processing.value = true
  progress.value = 0
  progressMessage.value = 'Uploading...'
  exportHint.value = ''
  fromHistory.value = false
  liveInfo.value = { done: 0, total: 0 }
}

function onUploadSuccess(jobData) {
  jobId.value = jobData.job_id
  progressMessage.value = 'Processing...'
  fromHistory.value = false
  processing.value = true
  result.value = {
    job_id: jobData.job_id,
    video_name: jobData.video_name || '',
    total_duration: 0,
    segments: [],
    complete: false,
  }

  connectSSE(
    jobData.job_id,
    (data) => {
      applyLivePayload(data)

      if (data.status === 'done' || data.event === 'done') {
        if (Array.isArray(data.segments) && data.segments.length) {
          applyResultData({
            job_id: jobData.job_id,
            video_name: data.video_name || result.value?.video_name || '',
            total_duration: data.total_duration || result.value?.total_duration || 0,
            segments: data.segments,
            complete: true,
          })
        } else {
          fetchResult(jobData.job_id, { keepProcessing: false })
        }
      } else if (data.status === 'failed' || data.event === 'failed') {
        processing.value = false
        error.value = data.message || 'Processing failed'
      }
    },
    () => {
      fetchResult(jobData.job_id, { keepProcessing: true })
    },
  )
}

async function fetchResult(id, { keepProcessing = false } = {}) {
  try {
    const res = await getJobResult(id)
    const data = res.data
    if (data?.complete === false && keepProcessing) {
      applyResultData(data, { keepProcessing: true })
      processing.value = true
      return
    }
    applyResultData(data)
  } catch (e) {
    if (e?.response?.status === 401) {
      user.value = null
      loginHint.value = '登录已过期，请重新登录'
      return
    }
    if (e?.response?.status === 202) {
      // 仍在处理且暂无片段
      return
    }
    if (!keepProcessing) {
      error.value = 'Failed to fetch results'
      processing.value = false
    }
  }
}

async function onSelectHistory(item) {
  if (!item?.job_id) return
  if (item.status === 'failed') {
    error.value = item.message || '该任务识别失败'
    result.value = null
    segments.value = []
    jobId.value = item.job_id
    fromHistory.value = true
    processing.value = false
    return
  }

  error.value = ''
  exportHint.value = ''
  jobId.value = item.job_id
  fromHistory.value = true
  const isLive = item.status === 'processing' || item.status === 'pending'
  processing.value = isLive
  liveInfo.value = {
    done: item.segment_count || 0,
    total: item.segment_count || 0,
  }

  try {
    const res = await getHistoryResult(item.job_id)
    applyResultData(res.data, { keepProcessing: isLive })
  } catch (e) {
    // 处理中可能只有 partial / 202
    if (isLive) {
      try {
        const res = await getJobResult(item.job_id)
        applyResultData(res.data, { keepProcessing: res.data?.complete === false })
        if (res.data?.complete === false) {
          result.value = {
            ...(res.data || {}),
            video_name: res.data.video_name || item.video_name || '',
          }
        }
        return
      } catch (e2) {
        result.value = {
          job_id: item.job_id,
          video_name: item.video_name || '',
          total_duration: item.total_duration || 0,
          segments: [],
          complete: false,
        }
        segments.value = []
        progressMessage.value = item.message || '识别中…'
        return
      }
    }
    result.value = null
    segments.value = []
    error.value = e?.response?.data?.detail || '历史结果加载失败'
  }
}

function openInUpload() {
  if (!result.value) return
  mode.value = 'upload'
  fromHistory.value = true
}

function onUploadError(msg) {
  processing.value = false
  error.value = msg
}

function onUpdateLabel({ index, label }) {
  const i = segments.value.findIndex((s) => s.index === index)
  if (i < 0) return
  segments.value[i] = applyLabelEdit(segments.value[i], labelMode.value, label)
  exportHint.value = '导出将使用当前编辑后的情感标签与识别文本'
}

function onUpdateText({ index, text }) {
  const i = segments.value.findIndex((s) => s.index === index)
  if (i < 0) return
  segments.value[i] = applyTextEdit(segments.value[i], text)
  exportHint.value = '导出将使用当前编辑后的情感标签与识别文本'
}

function onExportCsv() {
  if (!segments.value.length) return
  exportCsv({
    segments: segments.value,
    videoName: result.value?.video_name || 'result',
    labelMode: labelMode.value,
  })
  exportHint.value = '已导出 CSV（含编辑后的情感与文本）'
}

async function onExportExcel() {
  if (!segments.value.length || !jobId.value) return
  exporting.value = 'excel'
  exportHint.value = ''
  try {
    await exportExcel({
      jobId: jobId.value,
      segments: segments.value,
      videoName: result.value?.video_name || '',
      labelMode: labelMode.value,
      requestFn: exportExcelWithEdits,
    })
    exportHint.value = '已导出 Excel（含编辑后的情感与文本）'
  } catch (e) {
    exportHint.value = 'Excel 导出失败，请重试'
  } finally {
    exporting.value = ''
  }
}

function onLoginSuccess(data) {
  user.value = data
  loginHint.value = ''
  mode.value = 'upload'
  historyPanelRef.value?.reload?.()
}

async function onLogout() {
  try {
    await logout()
  } catch (_) {
    // ignore
  }
  user.value = null
  result.value = null
  jobId.value = ''
  segments.value = []
  processing.value = false
  mode.value = 'upload'
  loginHint.value = ''
}

onMounted(async () => {
  try {
    const res = await fetchMe()
    user.value = res.data
    loginHint.value = '默认账号：account / password（用户文件：storage/users.json）'
  } catch (_) {
    user.value = null
    loginHint.value = '请使用账号 account / password 登录'
  } finally {
    authChecked.value = true
  }
})
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: #f5f5f7;
  color: #333;
}
.app { min-height: 100vh; }
.app-header {
  background: #fff;
  padding: 16px 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 24px;
}
.app-header h1 { font-size: 18px; font-weight: 600; }
.mode-tabs { display: flex; gap: 4px; flex: 1; }
.tab {
  padding: 6px 16px;
  border: 1px solid #ddd;
  border-radius: 8px;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.tab:hover { border-color: #007AFF; color: #007AFF; }
.tab:focus-visible { outline: 2px solid #007AFF; outline-offset: 2px; }
.tab.active { background: #007AFF; color: #fff; border-color: #007AFF; }

.user-area {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}
.user-name {
  font-size: 13px;
  color: #555;
  font-weight: 600;
}
.logout-btn {
  border: 1px solid #ddd;
  background: #fff;
  border-radius: 8px;
  padding: 5px 12px;
  font-size: 12px;
  cursor: pointer;
  color: #666;
}
.logout-btn:hover { border-color: #FF3B30; color: #FF3B30; }

.app-main {
  max-width: 1400px;
  margin: 24px auto;
  padding: 0 20px 40px;
}
.auth-loading {
  text-align: center;
  color: #8E8E93;
  padding: 60px 0;
  font-size: 14px;
}

.workspace {
  display: grid;
  grid-template-columns: minmax(320px, 1fr) minmax(360px, 1.1fr);
  gap: 16px;
  align-items: start;
}
.history-layout {
  display: grid;
  grid-template-columns: minmax(300px, 0.9fr) minmax(360px, 1.2fr);
  gap: 16px;
  align-items: start;
}
.panel {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.panel-left,
.panel-right { min-height: 280px; }

.left-placeholder,
.right-placeholder {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  padding: 24px;
}
.right-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  min-height: 280px;
  color: #8E8E93;
  border: 1px dashed #e0e0e0;
}
.placeholder-icon { font-size: 36px; margin-bottom: 12px; }
.placeholder-title { font-size: 15px; font-weight: 600; color: #555; margin-bottom: 6px; }
.placeholder-hint { font-size: 13px; color: #999; }
.right-placeholder.processing { border-style: solid; border-color: #e8f0ff; background: #f8fbff; }
.mini-progress {
  width: 70%;
  max-width: 240px;
  height: 8px;
  background: #e9ecef;
  border-radius: 4px;
  overflow: hidden;
  margin-top: 16px;
}
.mini-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #007AFF, #5ac8fa);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.left-stack { display: flex; flex-direction: column; gap: 16px; }

.error-banner {
  background: #fff0f0;
  border: 1px solid #ffcdd2;
  border-radius: 8px;
  padding: 12px 16px;
  color: #c62828;
  font-size: 14px;
}

.result-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  background: #fff;
  border-radius: 12px;
  padding: 12px 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.mode-toggle { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.mode-label { font-size: 13px; color: #666; }
.mode-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 16px;
  background: #eef5ff;
  color: #007AFF;
  font-size: 12px;
  font-weight: 500;
}
.history-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 16px;
  background: #fff4e5;
  color: #FF9500;
  font-size: 12px;
  font-weight: 500;
}
.live-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 16px;
  background: #e8f8ee;
  color: #34C759;
  font-size: 12px;
  font-weight: 600;
}
.live-progress {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  border-radius: 12px;
  padding: 10px 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.live-progress-bar {
  flex: 0 0 160px;
  height: 8px;
  background: #e9ecef;
  border-radius: 4px;
  overflow: hidden;
}
.live-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #34C759, #5ac8fa);
  border-radius: 4px;
  transition: width 0.25s ease;
}
.live-progress-text {
  font-size: 12px;
  color: #666;
}
.mode-btn {
  padding: 4px 14px;
  border: 1px solid #ddd;
  border-radius: 16px;
  background: #fff;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.mode-btn:hover { border-color: #007AFF; color: #007AFF; }
.mode-btn:focus-visible { outline: 2px solid #007AFF; outline-offset: 2px; }
.mode-btn.active { background: #007AFF; color: #fff; border-color: #007AFF; }

.export-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.export-btn {
  padding: 6px 14px;
  border-radius: 16px;
  font-size: 12px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s;
  background: #fff;
}
.export-btn:focus-visible { outline: 2px solid #007AFF; outline-offset: 2px; }
.export-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.export-btn.csv {
  border-color: #34C759;
  color: #34C759;
  background: #fff;
}
.export-btn.csv:hover:not(:disabled) { background: #34C759; color: #fff; }
.export-btn.excel {
  background: #34C759;
  color: #fff;
  border-color: #34C759;
}
.export-btn.excel:hover:not(:disabled) { background: #2DA44E; }
.export-btn.open {
  border-color: #007AFF;
  color: #007AFF;
}
.export-btn.open:hover { background: #007AFF; color: #fff; }

.export-hint {
  font-size: 12px;
  color: #666;
  margin: -4px 4px 0;
}

@media (max-width: 960px) {
  .workspace,
  .history-layout {
    grid-template-columns: 1fr;
  }
  .app-main { padding: 0 12px 32px; }
  .app-header { flex-wrap: wrap; gap: 12px; }
}
</style>
