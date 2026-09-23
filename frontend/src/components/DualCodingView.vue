<template>
  <div class="dual-view">
    <div class="workspace">
      <!-- 左侧：上传 / 进度 / 视频 -->
      <section class="panel panel-left">
        <div v-if="!jobId" class="left-placeholder">
          <div class="intro-card">
            <h2>教学情绪-行为双维自动编码</h2>
            <p>
              面向微格/模拟教学视频，按论文第三章编码体系自动输出
              <strong>教学行为编码（B1–B15）</strong>与
              <strong>可观察教学情绪编码（E1–E3 / U1 / N1–N2 / X0）</strong>，
              共用同一时间轴，支持人工复核并导出标准化双维编码表。
            </p>
            <ul class="principles">
              <li>行为按教学功能判断，不单靠关键词</li>
              <li>情绪只识别外显状态，不猜测内心情绪</li>
              <li>无法可靠观察时保留 X0</li>
              <li>事件抽样 + 情绪变化切分编码单元</li>
            </ul>
            <p class="tech-note">ASR 与多模态识别由阿里云（DashScope / Qwen-VL）提供</p>
          </div>
          <VideoUpload
            :disabled="processing"
            :upload-fn="uploadDualVideo"
            hint="上传微格/模拟教学视频（mp4, avi, mov, mkv）"
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

          <div class="video-card">
            <h3 class="card-title">原始视频</h3>
            <video
              ref="videoEl"
              :src="videoUrl"
              controls
              class="video-player"
            ></video>
          </div>
        </div>
      </section>

      <!-- 右侧：双维结果 -->
      <section class="panel panel-right">
        <div v-if="error && !jobId" class="error-banner">{{ error }}</div>

        <div v-if="!units.length && processing" class="right-placeholder processing">
          <div class="placeholder-icon">⏳</div>
          <p class="placeholder-title">正在进行双维自动编码…</p>
          <p class="placeholder-hint">{{ progressMessage || '语音识别 → 逐段多模态编码 → 实时展示' }}</p>
          <div class="mini-progress">
            <div class="mini-progress-fill" :style="{ width: (progress * 100) + '%' }"></div>
          </div>
        </div>

        <div v-else-if="!units.length" class="right-placeholder">
          <div class="placeholder-icon">🎬</div>
          <p class="placeholder-title">双维编码结果将显示在这里</p>
          <p class="placeholder-hint">一个编码单元 = 一个行为码 + 一个情绪码；可人工复核后导出标准化编码表</p>
        </div>

        <template v-else>
          <div class="result-toolbar">
            <div class="mode-toggle">
              <span class="mode-label">{{ result?.video_name || jobId }}</span>
              <span class="mode-badge">情绪-行为双维编码</span>
              <span v-if="fromHistory" class="history-badge">历史记录</span>
              <span v-if="processing" class="live-badge">
                识别中 · 已展示 {{ units.length }} 段
              </span>
              <span v-if="reviewPending" class="review-badge">待复核 {{ reviewPending }}</span>
            </div>
            <div class="export-actions">
              <button
                class="export-btn csv"
                :disabled="!!exporting || !units.length"
                @click="onExportCsv"
              >
                {{ exporting === 'csv' ? '导出中…' : '导出 CSV' }}
              </button>
              <button
                class="export-btn excel"
                :disabled="!!exporting || !units.length || !jobId"
                @click="onExportExcel"
              >
                {{ exporting === 'excel' ? '导出中…' : '导出 Excel' }}
              </button>
              <button class="export-btn" @click="resetAll">新建分析</button>
            </div>
          </div>

          <div v-if="processing" class="live-progress">
            <div class="live-progress-bar">
              <div class="live-progress-fill" :style="{ width: (progress * 100) + '%' }"></div>
            </div>
            <span class="live-progress-text">{{ progressMessage || '处理中…' }}</span>
          </div>

          <p v-if="exportHint" class="export-hint">{{ exportHint }}</p>
          <p v-else-if="processing" class="export-hint">
            完成一段展示一段，可边识别边复核；结束后自动汇总指标
          </p>

          <DualTimeline
            :units="units"
            :total-duration="result?.total_duration || 0"
            @seek="onSeek"
          />

          <div v-if="result?.summary" class="metrics-bar">
            <span v-for="(val, key) in metricItems" :key="key" class="metric">
              {{ key }} {{ (val * 100).toFixed(1) }}%
            </span>
          </div>

          <DualResultTable
            :units="units"
            @update-behavior="onUpdateBehavior"
            @update-emotion="onUpdateEmotion"
            @update-text="onUpdateText"
            @update-review="onUpdateReview"
          />
        </template>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import VideoUpload from './VideoUpload.vue'
import ProgressPanel from './ProgressPanel.vue'
import DualTimeline from './DualTimeline.vue'
import DualResultTable from './DualResultTable.vue'
import {
  connectDualSSE,
  exportDualExcelWithEdits,
  getDualJobResult,
  getDualOriginalVideoUrl,
  getHistoryDualResult,
  uploadDualVideo,
} from '../api.js'
import {
  applyBehaviorEdit,
  applyEmotionEdit,
  applyReviewMark,
  applyTextEdit,
  mapDualUnit,
} from '../dualConfig.js'
import { buildDualExportPayload, exportDualCsv } from '../dualExportUtils.js'

const processing = ref(false)
const progress = ref(0)
const progressMessage = ref('')
const jobStatus = ref('')
const error = ref('')
const result = ref(null)
const jobId = ref('')
const fromHistory = ref(false)
const units = ref([])
const exporting = ref(null) // null | 'csv' | 'excel'；勿用 ''，Vue 会把空串当成 disabled
const exportHint = ref('')
const liveInfo = ref({ done: 0, total: 0 })
const videoEl = ref(null)

let eventSource = null

const videoUrl = computed(() => (jobId.value ? getDualOriginalVideoUrl(jobId.value) : ''))

const reviewPending = computed(
  () => units.value.filter((u) => u.needs_review && !u.review_marked).length
)

const metricItems = computed(() => {
  const s = result.value?.summary || {}
  const keys = ['KPBR', 'IIBR', 'IOBR', 'COBR', 'TEOR', 'PER', 'NER', 'NGR']
  const out = {}
  for (const k of keys) {
    if (typeof s[k] === 'number') out[k] = s[k]
  }
  return out
})

function closeSSE() {
  if (eventSource) {
    try {
      eventSource.close()
    } catch (_) {
      /* ignore */
    }
    eventSource = null
  }
}

function mapOne(unit) {
  return mapDualUnit(unit)
}

function preserveEdits(prev, next) {
  if (!prev) return mapOne(next)
  return {
    ...mapOne(next),
    text: (prev.text ?? '') !== (prev.original_text ?? '') ? prev.text : next.text,
    behavior_code: prev.behavior_code !== prev.original_behavior_code ? prev.behavior_code : next.behavior_code,
    behavior_name: prev.behavior_code !== prev.original_behavior_code ? prev.behavior_name : next.behavior_name,
    behavior_dim: prev.behavior_code !== prev.original_behavior_code ? prev.behavior_dim : next.behavior_dim,
    emotion_code: prev.emotion_code !== prev.original_emotion_code ? prev.emotion_code : next.emotion_code,
    emotion_name: prev.emotion_code !== prev.original_emotion_code ? prev.emotion_name : next.emotion_name,
    emotion_dim: prev.emotion_code !== prev.original_emotion_code ? prev.emotion_dim : next.emotion_dim,
    review_marked: !!prev.review_marked,
  }
}

function upsertUnits(raw) {
  const prevMap = new Map(units.value.map((u) => [u.index, u]))
  const next = (raw || []).map((u) => preserveEdits(prevMap.get(u.index), mapOne(u)))
  next.sort((a, b) => a.index - b.index)
  units.value = next
  syncShell()
}

function syncShell() {
  if (!units.value.length && !jobId.value) {
    result.value = null
    return
  }
  const base = result.value || {}
  result.value = {
    job_id: jobId.value || base.job_id || '',
    video_name: base.video_name || '',
    total_duration: base.total_duration || 0,
    units: units.value,
    summary: base.summary || {},
    sequences: base.sequences || {},
    complete: !processing.value,
  }
}

function applyLivePayload(data) {
  progress.value = data.progress ?? progress.value
  progressMessage.value = data.message || progressMessage.value
  jobStatus.value = data.status || jobStatus.value

  if (data.video_name) {
    result.value = {
      ...(result.value || {}),
      job_id: jobId.value || data.job_id || '',
      video_name: data.video_name,
      total_duration: data.total_duration || result.value?.total_duration || 0,
      units: units.value,
      summary: result.value?.summary || {},
      complete: false,
    }
  }
  if (data.total_duration && result.value) {
    result.value = { ...result.value, total_duration: data.total_duration }
  }

  if (Array.isArray(data.units)) {
    upsertUnits(data.units)
  }
  if (data.unit) {
    const prevMap = new Map(units.value.map((u) => [u.index, u]))
    const mapped = preserveEdits(prevMap.get(data.unit.index), mapOne(data.unit))
    const arr = units.value.filter((u) => u.index !== mapped.index)
    arr.push(mapped)
    arr.sort((a, b) => a.index - b.index)
    units.value = arr
    syncShell()
  }
  if (Array.isArray(data.units) && data.units.length && data.event === 'unit') {
    // 偶发整包推送时也按 index 合并，避免闪烁
    upsertUnits(data.units)
  }

  liveInfo.value = {
    done: data.units_done ?? units.value.length,
    total: data.units_total ?? liveInfo.value.total,
  }
}

function applyResultData(data, { keepProcessing = false } = {}) {
  const prevMap = new Map(units.value.map((u) => [u.index, u]))
  const mapped = (data.units || []).map((u) => preserveEdits(prevMap.get(u.index), mapOne(u)))
  result.value = { ...data, units: mapped }
  units.value = mapped
  if (!keepProcessing) {
    processing.value = false
    if (data.complete !== false) {
      liveInfo.value = { done: mapped.length, total: mapped.length }
    }
    exportHint.value = ''
  } else if (Array.isArray(data.units)) {
    liveInfo.value = {
      done: data.units.length,
      total: liveInfo.value.total || data.units.length,
    }
  }
  error.value = ''
}

function onUploadStart() {
  error.value = ''
  result.value = null
  jobId.value = ''
  units.value = []
  processing.value = true
  progress.value = 0
  progressMessage.value = 'Uploading...'
  exportHint.value = ''
  fromHistory.value = false
  liveInfo.value = { done: 0, total: 0 }
}

function onUploadSuccess(status) {
  const id = status?.job_id
  if (!id) {
    processing.value = false
    error.value = '上传成功但未返回任务 ID'
    return
  }
  jobId.value = id
  progress.value = status.progress || 0.02
  progressMessage.value = status.message || 'Queued'
  jobStatus.value = status.status || 'pending'
  watchJob(id)
}

function onUploadError(msg) {
  processing.value = false
  error.value = msg || '上传失败'
  progressMessage.value = ''
}

function watchJob(id) {
  closeSSE()
  eventSource = connectDualSSE(
    id,
    (data) => {
      applyLivePayload(data)
      if (data.status === 'done') {
        processing.value = false
        getDualJobResult(id)
          .then((res) => applyResultData(res.data))
          .catch(() => {})
        exportHint.value = ''
      } else if (data.status === 'failed') {
        processing.value = false
        error.value = data.message || '识别失败'
      }
    },
    () => {
      // SSE 断开后拉一次结果兜底
      getDualJobResult(id)
        .then((res) => {
          applyResultData(res.data, { keepProcessing: processing.value })
          if (res.data?.complete) processing.value = false
        })
        .catch(() => {})
    }
  )
}

function openHistoryItem(item) {
  const id = item?.job_id
  if (!id) return
  closeSSE()
  jobId.value = id
  fromHistory.value = true
  error.value = ''
  exportHint.value = ''
  processing.value = item.status === 'processing' || item.status === 'pending'
  progress.value = processing.value ? (item.status === 'done' ? 1 : 0.3) : 1
  progressMessage.value = item.message || ''
  jobStatus.value = item.status || ''
  units.value = []
  result.value = null

  getHistoryDualResult(id)
    .then((res) => {
      applyResultData(res.data, { keepProcessing: processing.value })
    })
    .catch((err) => {
      if (err?.response?.status === 202) {
        watchJob(id)
        return
      }
      error.value = err?.response?.data?.detail || '加载历史结果失败'
      processing.value = false
    })

  if (processing.value) {
    watchJob(id)
  }
}

function replaceUnit(index, updater) {
  const idx = units.value.findIndex((u) => u.index === index)
  if (idx < 0) return
  const next = updater(units.value[idx])
  const arr = units.value.slice()
  arr[idx] = next
  units.value = arr
  syncShell()
}

function onUpdateBehavior({ index, code }) {
  replaceUnit(index, (u) => applyBehaviorEdit(u, code))
}

function onUpdateEmotion({ index, code }) {
  replaceUnit(index, (u) => applyEmotionEdit(u, code))
}

function onUpdateText({ index, text }) {
  replaceUnit(index, (u) => applyTextEdit(u, text))
}

function onUpdateReview({ index, marked }) {
  replaceUnit(index, (u) => applyReviewMark(u, marked))
}

function onSeek(time) {
  if (videoEl.value) {
    videoEl.value.currentTime = time
    videoEl.value.play()
  }
}

function resetAll() {
  closeSSE()
  jobId.value = ''
  units.value = []
  result.value = null
  processing.value = false
  progress.value = 0
  progressMessage.value = ''
  error.value = ''
  fromHistory.value = false
  exportHint.value = ''
  liveInfo.value = { done: 0, total: 0 }
}

function onExportCsv() {
  if (!units.value.length) {
    exportHint.value = '没有可导出的编码单元'
    return
  }
  exporting.value = 'csv'
  exportHint.value = ''
  try {
    exportDualCsv({ units: units.value, videoName: result.value?.video_name || 'dual_coding' })
    exportHint.value = `已导出 CSV（${units.value.length} 条编码单元）`
  } catch (e) {
    console.error('CSV export failed:', e)
    exportHint.value = 'CSV 导出失败: ' + (e?.message || e)
  } finally {
    exporting.value = null
  }
}

async function onExportExcel() {
  if (!units.value.length || !jobId.value) {
    exportHint.value = '没有可导出的编码结果'
    return
  }
  exporting.value = 'excel'
  exportHint.value = ''
  try {
    const payload = buildDualExportPayload({
      units: units.value,
      videoName: result.value?.video_name || '',
    })
    const res = await exportDualExcelWithEdits(jobId.value, payload)
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    // 若后端返回 JSON 错误却配了 blob，这里识别出来
    if (blob.type && blob.type.includes('application/json')) {
      const text = await blob.text()
      throw new Error(text.slice(0, 200))
    }
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${(result.value?.video_name || 'dual_coding').replace(/\.[^.]+$/, '')}_双维编码表.xlsx`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    exportHint.value = `Excel 已导出（${units.value.length} 条，含编码手册/指标/矩阵）`
  } catch (e) {
    console.error('Excel export failed:', e)
    let msg = e?.response?.data?.detail || e?.message || String(e)
    const data = e?.response?.data
    if (data instanceof Blob) {
      try {
        const text = await data.text()
        try {
          const j = JSON.parse(text)
          msg = j.detail || text
        } catch {
          msg = text.slice(0, 300) || msg
        }
      } catch (_) { /* ignore */ }
    } else if (data && typeof data === 'object' && data.detail) {
      msg = data.detail
    }
    exportHint.value = 'Excel 导出失败: ' + msg
  } finally {
    exporting.value = null
  }
}

onBeforeUnmount(() => {
  closeSSE()
})

defineExpose({ openHistoryItem, resetAll })
</script>

<style scoped>
.dual-view {
  height: 100%;
}
.workspace {
  display: grid;
  grid-template-columns: minmax(280px, 0.9fr) 1.4fr;
  gap: 16px;
  align-items: start;
}
.panel {
  min-width: 0;
}
.left-placeholder {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.intro-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px 22px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.intro-card h2 {
  margin: 0 0 10px;
  font-size: 18px;
  color: #1f2a37;
}
.intro-card p {
  margin: 0 0 10px;
  font-size: 13px;
  color: #444;
  line-height: 1.6;
}
.principles {
  margin: 0 0 10px;
  padding-left: 18px;
  font-size: 13px;
  color: #555;
  line-height: 1.7;
}
.tech-note {
  font-size: 12px;
  color: #888;
  margin: 0;
}
.left-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.video-card,
.right-placeholder {
  background: #fff;
  border-radius: 12px;
  padding: 16px 18px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.card-title {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 600;
  color: #333;
}
.video-player {
  width: 100%;
  border-radius: 8px;
  background: #000;
}
.right-placeholder {
  text-align: center;
  padding: 48px 24px;
}
.right-placeholder.processing {
  background: #f8fbff;
}
.placeholder-icon {
  font-size: 40px;
  margin-bottom: 8px;
}
.placeholder-title {
  margin: 0 0 6px;
  font-size: 16px;
  color: #333;
}
.placeholder-hint {
  margin: 0;
  font-size: 13px;
  color: #888;
}
.mini-progress {
  margin: 16px auto 0;
  max-width: 280px;
  height: 6px;
  background: #e8e8ed;
  border-radius: 3px;
  overflow: hidden;
}
.mini-progress-fill {
  height: 100%;
  background: #0a84ff;
  transition: width 0.2s;
}
.result-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}
.mode-toggle {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.mode-label {
  font-weight: 600;
  color: #333;
  font-size: 14px;
}
.mode-badge,
.history-badge,
.live-badge,
.review-badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
}
.mode-badge {
  background: #eef5ff;
  color: #0a84ff;
}
.history-badge {
  background: #f2f2f7;
  color: #666;
}
.live-badge {
  background: #e8f8ef;
  color: #28a745;
}
.review-badge {
  background: #fff4e5;
  color: #ff9f0a;
}
.export-actions {
  display: flex;
  gap: 8px;
}
.export-btn {
  border: 1px solid #d0d0d5;
  background: #fff;
  color: #333;
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
}
.export-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.export-btn.csv:hover {
  border-color: #34c759;
  color: #34c759;
}
.export-btn.excel:hover {
  border-color: #0a84ff;
  color: #0a84ff;
}
.live-progress {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.live-progress-bar {
  flex: 1;
  height: 6px;
  background: #e8e8ed;
  border-radius: 3px;
  overflow: hidden;
}
.live-progress-fill {
  height: 100%;
  background: #0a84ff;
}
.live-progress-text {
  font-size: 12px;
  color: #666;
  white-space: nowrap;
}
.export-hint {
  font-size: 12px;
  color: #888;
  margin: 0 0 8px;
}
.error-banner {
  background: #ffecec;
  color: #c0392b;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 10px;
  font-size: 13px;
}
.metrics-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.metric {
  font-size: 12px;
  background: #f5f5f7;
  color: #444;
  border-radius: 8px;
  padding: 4px 8px;
}
@media (max-width: 980px) {
  .workspace {
    grid-template-columns: 1fr;
  }
}
</style>
