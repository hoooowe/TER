<template>
  <div v-if="segments.length" class="result-container">
    <div class="result-header">
      <h3 class="result-title">
        识别结果
        <span v-if="editedCount" class="edited-count">已修改 {{ editedCount }} 条</span>
        <span v-if="textEditedCount" class="edited-count text">文本已改 {{ textEditedCount }} 条</span>
      </h3>
      <div class="filter-buttons">
        <button
          v-for="(name, key) in names"
          :key="key"
          class="filter-btn"
          :class="{ active: activeFilter === null || activeFilter === Number(key) }"
          :style="activeFilter === Number(key) ? { background: colors[key], color: '#fff' } : {}"
          @click="toggleFilter(Number(key))"
        >
          {{ name }}
        </button>
      </div>
    </div>

    <div class="table-wrap">
      <table class="result-table">
        <thead>
          <tr>
            <th>#</th>
            <th>时间段</th>
            <th>识别情感</th>
            <th>最终情感（可编辑）</th>
            <th>置信度</th>
            <th>文本（可编辑）</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="seg in filteredSegments"
            :key="seg.index"
            :class="{ edited: isEdited(seg) || isTextEdited(seg) }"
          >
            <td>{{ seg.index + 1 }}</td>
            <td class="time-cell">{{ formatTime(seg.start_time) }} - {{ formatTime(seg.end_time) }}</td>
            <td>
              <span
                class="emotion-badge original"
                :style="{ background: colors[getOriginalLabel(seg, labelMode)] || '#8E8E93' }"
              >
                {{ getOriginalLabelName(seg, labelMode) }}
              </span>
            </td>
            <td class="edit-cell">
              <select
                class="emotion-select"
                :value="getLabel(seg, labelMode)"
                :style="{
                  borderColor: colors[getLabel(seg, labelMode)] || '#ccc',
                  color: colors[getLabel(seg, labelMode)] || '#333',
                }"
                @change="onChange(seg, $event.target.value)"
              >
                <option
                  v-for="opt in options"
                  :key="opt.value"
                  :value="opt.value"
                >
                  {{ opt.label }}
                </option>
              </select>
              <span v-if="isEdited(seg)" class="edited-tag">已改</span>
            </td>
            <td class="confidence-cell">
              <div class="confidence-bar-bg">
                <div
                  class="confidence-bar-fill"
                  :style="{
                    width: ((seg.confidence || 0) * 100) + '%',
                    background: colors[getLabel(seg, labelMode)],
                  }"
                ></div>
              </div>
              <span class="confidence-text">{{ ((seg.confidence || 0) * 100).toFixed(0) }}%</span>
            </td>
            <td class="text-edit-cell">
              <textarea
                class="text-input"
                :class="{ edited: isTextEdited(seg) }"
                :value="seg.text"
                :title="isTextEdited(seg) ? `识别原文：${getOriginalText(seg)}` : seg.text"
                rows="2"
                @change="onTextChange(seg, $event.target.value)"
              ></textarea>
              <span v-if="isTextEdited(seg)" class="edited-tag">文本已改</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import {
  getColors,
  getNames,
  getLabel,
  getLabelName,
  getOriginalLabel,
  getOriginalLabelName,
  getOriginalText,
  isLabelEdited,
  isTextEdited,
  getLabelOptions,
  formatTime,
} from '../emotionConfig.js'

const props = defineProps({
  segments: { type: Array, default: () => [] },
  labelMode: { type: String, default: 'e2v' },
})

const emit = defineEmits(['update-label', 'update-text'])

const activeFilter = ref(null)

const colors = computed(() => getColors(props.labelMode))
const names = computed(() => getNames(props.labelMode))
const options = computed(() => getLabelOptions(props.labelMode))

const editedCount = computed(() =>
  props.segments.filter((s) => isLabelEdited(s, props.labelMode)).length
)

const textEditedCount = computed(() =>
  props.segments.filter((s) => isTextEdited(s)).length
)

const filteredSegments = computed(() => {
  if (activeFilter.value === null) return props.segments
  return props.segments.filter((s) => getLabel(s, props.labelMode) === activeFilter.value)
})

function isEdited(seg) {
  return isLabelEdited(seg, props.labelMode)
}

function onChange(seg, rawValue) {
  const next = Number(rawValue)
  if (Number.isNaN(next)) return
  emit('update-label', { index: seg.index, label: next })
}

function onTextChange(seg, value) {
  const next = value ?? ''
  if (next === (seg.text ?? '')) return
  emit('update-text', { index: seg.index, text: next })
}

function toggleFilter(label) {
  activeFilter.value = activeFilter.value === label ? null : label
}
</script>

<style scoped>
.result-container {
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}
.result-title {
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
  font-weight: 500;
  color: #FF9500;
  background: #fff4e5;
  padding: 2px 8px;
  border-radius: 10px;
}
.edited-count.text {
  color: #007AFF;
  background: #eef5ff;
}
.filter-buttons {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.filter-btn {
  padding: 4px 12px;
  border: 1px solid #ddd;
  border-radius: 16px;
  background: #fff;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.filter-btn:hover { border-color: #007AFF; }
.filter-btn:focus-visible { outline: 2px solid #007AFF; outline-offset: 2px; }
.filter-btn.active { border-color: transparent; }

.table-wrap { overflow-x: auto; }

.result-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  min-width: 640px;
}
.result-table th {
  text-align: left;
  padding: 10px 8px;
  border-bottom: 2px solid #eee;
  color: #666;
  font-weight: 600;
  white-space: nowrap;
}
.result-table td {
  padding: 10px 8px;
  border-bottom: 1px solid #f0f0f0;
  vertical-align: middle;
}
.result-table tr.edited td { background: #fffaf0; }

.time-cell { white-space: nowrap; color: #555; }

.emotion-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 12px;
  color: #fff;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}
.emotion-badge.original { opacity: 0.85; }

.edit-cell { white-space: nowrap; }
.emotion-select {
  min-width: 110px;
  padding: 6px 10px;
  border: 1.5px solid #ddd;
  border-radius: 8px;
  background: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.emotion-select:hover { box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.12); }
.emotion-select:focus-visible {
  box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.25);
  border-color: #007AFF;
}
.edited-tag {
  margin-left: 6px;
  font-size: 11px;
  color: #FF9500;
  background: #fff4e5;
  padding: 1px 6px;
  border-radius: 8px;
}

.confidence-cell { min-width: 100px; }
.confidence-bar-bg {
  display: inline-block;
  width: 50px;
  height: 6px;
  background: #eee;
  border-radius: 3px;
  vertical-align: middle;
  margin-right: 6px;
}
.confidence-bar-fill { height: 100%; border-radius: 3px; }
.confidence-text { font-size: 12px; color: #666; }

.text-edit-cell {
  min-width: 220px;
  max-width: 280px;
}
.text-input {
  width: 100%;
  min-height: 48px;
  padding: 6px 8px;
  border: 1.5px solid #e5e5ea;
  border-radius: 8px;
  background: #fff;
  color: #555;
  font-size: 13px;
  font-family: inherit;
  line-height: 1.4;
  resize: vertical;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
}
.text-input:hover { border-color: #c7c7cc; }
.text-input:focus-visible {
  border-color: #007AFF;
  box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.2);
}
.text-input.edited {
  border-color: #007AFF;
  background: #f5f9ff;
}
</style>
