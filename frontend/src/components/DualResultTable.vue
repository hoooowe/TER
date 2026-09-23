<template>
  <div v-if="units.length" class="dual-table-wrap">
    <div class="table-header">
      <h3 class="table-title">
        双维编码表
        <span v-if="editedCount" class="edited-count">已修改 {{ editedCount }} 条</span>
        <span v-if="reviewCount" class="review-count">待复核 {{ reviewCount }} 条</span>
      </h3>
      <div class="filters">
        <button
          class="filter-btn"
          :class="{ active: filterType === 'review' }"
          @click="toggleReviewFilter"
        >
          仅看待复核
        </button>
        <button
          class="filter-btn"
          :class="{ active: filterType === 'edited' }"
          @click="toggleEditedFilter"
        >
          仅看已修改
        </button>
      </div>
    </div>

    <div class="table-scroll">
      <table class="dual-table">
        <thead>
          <tr>
            <th>#</th>
            <th>时间</th>
            <th>文本</th>
            <th>行为（可编辑）</th>
            <th>情绪（可编辑）</th>
            <th>判定依据</th>
            <th>置信</th>
            <th>复核</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="u in filtered"
            :key="u.index"
            :class="{ edited: isUnitEdited(u), review: u.needs_review && !u.review_marked }"
          >
            <td>{{ u.index + 1 }}</td>
            <td class="time-cell">{{ formatTime(u.start_time) }}-{{ formatTime(u.end_time) }}</td>
            <td class="text-cell">
              <textarea
                class="text-input"
                :class="{ edited: isTextEdited(u) }"
                :value="u.text"
                rows="2"
                :title="isTextEdited(u) ? `识别原文：${u.original_text}` : (u.text || '（无语音）')"
                @change="onText(u, $event.target.value)"
              ></textarea>
            </td>
            <td class="code-cell">
              <div class="code-row">
                <span class="code-badge original" :style="{ background: behaviorColor(u.original_behavior_code) }">
                  {{ u.original_behavior_code }}
                </span>
                <select
                  class="code-select"
                  :value="u.behavior_code"
                  :style="{ borderColor: behaviorColor(u.behavior_code) }"
                  @change="onBehavior(u, $event.target.value)"
                >
                  <option v-for="b in BEHAVIOR_CODES" :key="b.code" :value="b.code">
                    {{ b.code }} {{ b.name }}
                  </option>
                </select>
              </div>
              <div class="code-dim">{{ u.behavior_dim }} · {{ u.behavior_name }}</div>
              <span v-if="isBehaviorEdited(u)" class="edited-tag">已改</span>
            </td>
            <td class="code-cell">
              <div class="code-row">
                <span class="code-badge original" :style="{ background: emotionColor(u.original_emotion_code) }">
                  {{ u.original_emotion_code }}
                </span>
                <select
                  class="code-select"
                  :value="u.emotion_code"
                  :style="{ borderColor: emotionColor(u.emotion_code) }"
                  @change="onEmotion(u, $event.target.value)"
                >
                  <option v-for="e in EMOTION_CODES" :key="e.code" :value="e.code">
                    {{ e.code }} {{ e.name }}
                  </option>
                </select>
              </div>
              <div class="code-dim">{{ u.emotion_dim }} · {{ u.emotion_name }}</div>
              <span v-if="isEmotionEdited(u)" class="edited-tag">已改</span>
            </td>
            <td class="reason-cell">
              <div class="reason-line">行为：{{ u.behavior_reason || '—' }}</div>
              <div class="reason-line">情绪：{{ u.emotion_evidence || '—' }}</div>
            </td>
            <td class="conf-cell">{{ ((u.confidence || 0) * 100).toFixed(0) }}%</td>
            <td class="review-cell">
              <label class="review-check">
                <input
                  type="checkbox"
                  :checked="!!u.review_marked"
                  @change="onReview(u, $event.target.checked)"
                />
                已复核
              </label>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  BEHAVIOR_CODES,
  EMOTION_CODES,
  behaviorColor,
  emotionColor,
  formatTime,
  isBehaviorEdited,
  isEmotionEdited,
  isTextEdited,
  isUnitEdited,
} from '../dualConfig.js'

const props = defineProps({
  units: { type: Array, default: () => [] },
})
const emit = defineEmits(['update-behavior', 'update-emotion', 'update-text', 'update-review'])

const filterType = ref('') // '' | 'review' | 'edited'

const editedCount = computed(() => props.units.filter(isUnitEdited).length)
const reviewCount = computed(() => props.units.filter((u) => u.needs_review && !u.review_marked).length)

const filtered = computed(() => {
  if (filterType.value === 'review') {
    return props.units.filter((u) => u.needs_review && !u.review_marked)
  }
  if (filterType.value === 'edited') {
    return props.units.filter(isUnitEdited)
  }
  return props.units
})

function toggleReviewFilter() {
  filterType.value = filterType.value === 'review' ? '' : 'review'
}

function toggleEditedFilter() {
  filterType.value = filterType.value === 'edited' ? '' : 'edited'
}

function onBehavior(u, code) {
  if (code === u.behavior_code) return
  emit('update-behavior', { index: u.index, code })
}

function onEmotion(u, code) {
  if (code === u.emotion_code) return
  emit('update-emotion', { index: u.index, code })
}

function onText(u, text) {
  if ((text ?? '') === (u.text ?? '')) return
  emit('update-text', { index: u.index, text })
}

function onReview(u, marked) {
  emit('update-review', { index: u.index, marked })
}
</script>

<style scoped>
.dual-table-wrap {
  background: #fff;
  border-radius: 12px;
  padding: 16px 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 8px;
}
.table-title {
  font-size: 15px;
  font-weight: 600;
  color: #333;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.edited-count {
  font-size: 12px;
  color: #007AFF;
  background: #eef5ff;
  padding: 2px 8px;
  border-radius: 10px;
}
.review-count {
  font-size: 12px;
  color: #FF9F0A;
  background: #fff4e5;
  padding: 2px 8px;
  border-radius: 10px;
}
.filters {
  display: flex;
  gap: 6px;
}
.filter-btn {
  padding: 4px 12px;
  border: 1px solid #ddd;
  border-radius: 16px;
  background: #fff;
  font-size: 12px;
  cursor: pointer;
}
.filter-btn.active {
  border-color: #007AFF;
  background: #eef5ff;
  color: #007AFF;
}
.table-scroll {
  overflow-x: auto;
}
.dual-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  min-width: 960px;
}
.dual-table th {
  text-align: left;
  padding: 8px 6px;
  border-bottom: 2px solid #eee;
  color: #666;
  font-weight: 600;
  white-space: nowrap;
}
.dual-table td {
  padding: 8px 6px;
  border-bottom: 1px solid #f0f0f0;
  vertical-align: top;
}
.dual-table tr.edited td {
  background: #fffaf0;
}
.dual-table tr.review td {
  background: #fff8f0;
}
.time-cell {
  white-space: nowrap;
  color: #555;
  font-size: 12px;
}
.text-cell {
  min-width: 180px;
  max-width: 240px;
}
.text-input {
  width: 100%;
  min-height: 44px;
  padding: 4px 6px;
  border: 1.5px solid #e5e5ea;
  border-radius: 8px;
  font-size: 12px;
  font-family: inherit;
  line-height: 1.4;
  resize: vertical;
}
.text-input.edited {
  border-color: #007AFF;
  background: #f5f9ff;
}
.code-cell {
  min-width: 150px;
}
.code-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.code-badge {
  display: inline-block;
  min-width: 28px;
  text-align: center;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 4px;
  border-radius: 4px;
}
.code-select {
  min-width: 108px;
  padding: 4px 6px;
  border: 1.5px solid #ddd;
  border-radius: 6px;
  font-size: 12px;
  background: #fff;
}
.code-dim {
  margin-top: 4px;
  font-size: 11px;
  color: #888;
}
.reason-cell {
  min-width: 180px;
  max-width: 260px;
  font-size: 11px;
  color: #666;
  line-height: 1.45;
}
.reason-line + .reason-line {
  margin-top: 4px;
}
.conf-cell {
  white-space: nowrap;
  color: #666;
  font-size: 12px;
}
.review-cell {
  white-space: nowrap;
}
.review-check {
  font-size: 12px;
  color: #555;
  cursor: pointer;
}
.edited-tag {
  margin-top: 4px;
  display: inline-block;
  font-size: 11px;
  color: #007AFF;
  background: #eef5ff;
  padding: 1px 6px;
  border-radius: 8px;
}
</style>
