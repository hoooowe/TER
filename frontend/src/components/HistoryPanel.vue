<template>
  <div class="history-panel">
    <div class="history-header">
      <div>
        <h3>识别历史</h3>
        <p class="history-sub">仅显示当前账号的任务；点击可查看结果并导出</p>
      </div>
      <button class="refresh-btn" :disabled="loading" @click="load">
        {{ loading ? '加载中…' : '刷新' }}
      </button>
    </div>

    <p v-if="error" class="history-error">{{ error }}</p>

    <div v-else-if="!items.length && !loading" class="history-empty">
      暂无历史记录。上传视频完成识别后会出现在这里。
    </div>

    <div v-else class="history-list">
      <div
        v-for="item in items"
        :key="item.job_id"
        class="history-item"
        :class="{ active: item.job_id === activeJobId }"
      >
        <button class="item-main item-open" type="button" @click="$emit('select', item)">
          <div class="item-title">
            <span v-if="item.job_type === 'dual'" class="type-tag dual">双维</span>
            <span v-else class="type-tag">情感</span>
            {{ item.video_name || item.job_id }}
          </div>
          <div class="item-meta">
            <span class="status" :class="item.status">{{ statusText(item.status) }}</span>
            <span>{{ item.segment_count }} 段</span>
            <span>{{ formatDuration(item.total_duration) }}</span>
            <span>{{ formatTime(item.created_at) }}</span>
          </div>
        </button>
        <div class="item-actions">
          <button
            class="delete-btn"
            type="button"
            :disabled="deletingId === item.job_id"
            :title="deletingId === item.job_id ? '删除中…' : '删除该记录'"
            @click.stop="onDelete(item)"
          >
            {{ deletingId === item.job_id ? '…' : '删除' }}
          </button>
          <div class="item-arrow">›</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { deleteHistory, fetchHistory } from '../api.js'

const props = defineProps({
  activeJobId: { type: String, default: '' },
})
const emit = defineEmits(['select', 'loaded', 'deleted'])

const items = ref([])
const loading = ref(false)
const error = ref('')
const deletingId = ref('')

async function onDelete(item) {
  if (!item?.job_id || deletingId.value) return
  const name = item.video_name || item.job_id
  const ok = window.confirm(
    `确定删除识别记录「${name}」吗？\n将同时删除结果与对应上传视频，不可恢复。`
  )
  if (!ok) return
  deletingId.value = item.job_id
  error.value = ''
  try {
    await deleteHistory(item.job_id)
    items.value = items.value.filter((x) => x.job_id !== item.job_id)
    emit('deleted', item.job_id)
    emit('loaded', items.value)
  } catch (e) {
    error.value = e?.response?.data?.detail || '删除失败，请重试'
  } finally {
    deletingId.value = ''
  }
}

function statusText(status) {
  const map = {
    done: '已完成',
    processing: '处理中',
    pending: '排队中',
    failed: '失败',
  }
  return map[status] || status
}

function formatDuration(seconds) {
  const s = Math.max(0, Math.floor(Number(seconds) || 0))
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m}:${String(r).padStart(2, '0')}`
}

function formatTime(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    const pad = (n) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  } catch {
    return iso
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetchHistory()
    items.value = res.data || []
    emit('loaded', items.value)
  } catch (e) {
    error.value = e?.response?.data?.detail || '历史记录加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
defineExpose({ reload: load })
</script>

<style scoped>
.history-panel {
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.history-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}
.history-header h3 {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 600;
  color: #333;
}
.history-sub {
  margin: 0;
  font-size: 12px;
  color: #8E8E93;
}
.refresh-btn {
  border: 1px solid #ddd;
  background: #fff;
  border-radius: 16px;
  padding: 5px 12px;
  font-size: 12px;
  cursor: pointer;
  color: #555;
}
.refresh-btn:hover { border-color: #007AFF; color: #007AFF; }
.refresh-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.history-error {
  margin: 0;
  color: #c62828;
  background: #fff0f0;
  border: 1px solid #ffcdd2;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13px;
}
.history-empty {
  color: #8E8E93;
  font-size: 13px;
  text-align: center;
  padding: 28px 12px;
  border: 1px dashed #e5e5ea;
  border-radius: 10px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 560px;
  overflow: auto;
}
.history-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  text-align: left;
  border: 1px solid #ececf0;
  background: #fafafa;
  border-radius: 10px;
  padding: 12px 14px;
  transition: border-color 0.15s, background 0.15s;
}
.item-open {
  flex: 1;
  min-width: 0;
  text-align: left;
  background: transparent;
  border: none;
  padding: 0;
  cursor: pointer;
}
.item-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.delete-btn {
  border: 1px solid #ffcdd2;
  background: #fff5f5;
  color: #c62828;
  border-radius: 8px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
}
.delete-btn:hover:not(:disabled) {
  background: #c62828;
  border-color: #c62828;
  color: #fff;
}
.delete-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.history-item:hover { border-color: #007AFF; background: #f5f9ff; }
.history-item.active {
  border-color: #007AFF;
  background: #eef5ff;
}
.item-title {
  font-size: 14px;
  font-weight: 600;
  color: #222;
  margin-bottom: 6px;
  word-break: break-all;
}
.type-tag {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  color: #666;
  background: #ececf0;
  border-radius: 6px;
  padding: 1px 6px;
  margin-right: 6px;
  vertical-align: middle;
}
.type-tag.dual {
  color: #0a84ff;
  background: #eef5ff;
}
.item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: #8E8E93;
}
.status {
  font-weight: 600;
}
.status.done { color: #34C759; }
.status.processing { color: #007AFF; }
.status.pending { color: #FF9500; }
.status.failed { color: #FF3B30; }
.item-arrow {
  color: #c7c7cc;
  font-size: 22px;
  line-height: 1;
}
</style>
