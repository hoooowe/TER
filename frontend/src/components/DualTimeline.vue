<template>
  <div v-if="units.length" class="dual-timeline">
    <h3 class="timeline-title">双维时间轴 <span class="hint">上：行为 · 下：情绪</span></h3>

    <div class="lane">
      <span class="lane-label">行为</span>
      <div class="lane-bar">
        <div
          v-for="u in units"
          :key="'b' + u.index"
          class="lane-seg"
          :style="segStyle(u, behaviorColor(u.behavior_code), false)"
          :title="tooltip(u)"
          @mouseenter="hovered = u"
          @mouseleave="hovered = null"
          @click="$emit('seek', u.start_time)"
        ></div>
      </div>
    </div>

    <div class="lane">
      <span class="lane-label">情绪</span>
      <div class="lane-bar emotion">
        <div
          v-for="u in units"
          :key="'e' + u.index"
          class="lane-seg"
          :style="segStyle(u, emotionColor(u.emotion_code), !!u.needs_review)"
          :title="tooltip(u)"
          @mouseenter="hovered = u"
          @mouseleave="hovered = null"
          @click="$emit('seek', u.start_time)"
        ></div>
      </div>
    </div>

    <div class="timeline-labels">
      <span>{{ formatTime(0) }}</span>
      <span>{{ formatTime(totalDuration) }}</span>
    </div>

    <div class="legends">
      <div class="legend-block">
        <span class="legend-title">行为</span>
        <span v-for="b in BEHAVIOR_CODES" :key="b.code" class="legend-item">
          <span class="legend-dot" :style="{ background: b.color }"></span>{{ b.code }}
        </span>
      </div>
      <div class="legend-block">
        <span class="legend-title">情绪</span>
        <span v-for="e in EMOTION_CODES" :key="e.code" class="legend-item">
          <span class="legend-dot" :style="{ background: e.color }"></span>{{ e.code }}
        </span>
      </div>
    </div>

    <div v-if="hovered" class="tooltip-detail">
      <strong>{{ formatTime(hovered.start_time) }} - {{ formatTime(hovered.end_time) }}</strong>
      · {{ hovered.behavior_code }} {{ hovered.behavior_name }}
      · {{ hovered.emotion_code }} {{ hovered.emotion_name }}
      <span v-if="hovered.needs_review" class="review-tag">待复核</span>
      <br />
      <span class="tooltip-text">{{ hovered.text || '（无语音）' }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, toRefs } from 'vue'
import {
  BEHAVIOR_CODES,
  EMOTION_CODES,
  behaviorColor,
  emotionColor,
  formatTime,
} from '../dualConfig.js'

const props = defineProps({
  units: { type: Array, default: () => [] },
  totalDuration: { type: Number, default: 0 },
})
defineEmits(['seek'])

const { totalDuration } = toRefs(props)
const hovered = ref(null)

function segStyle(u, color, review) {
  const total = totalDuration.value || 1
  const left = (u.start_time / total) * 100
  const width = ((u.end_time - u.start_time) / total) * 100
  return {
    left: left + '%',
    width: Math.max(width, 0.4) + '%',
    background: color,
    opacity: review ? 0.55 : 0.92,
    outline: review ? '2px dashed #FF9F0A' : 'none',
  }
}

function tooltip(u) {
  return `${formatTime(u.start_time)}-${formatTime(u.end_time)}: ${u.behavior_code} ${u.behavior_name} / ${u.emotion_code} ${u.emotion_name}`
}
</script>

<style scoped>
.dual-timeline {
  background: #fff;
  border-radius: 12px;
  padding: 16px 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  margin-bottom: 12px;
}
.timeline-title {
  font-size: 15px;
  font-weight: 600;
  color: #333;
  margin: 0 0 12px;
}
.hint {
  font-size: 12px;
  font-weight: 400;
  color: #999;
  margin-left: 8px;
}
.lane {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.lane-label {
  width: 32px;
  font-size: 12px;
  color: #666;
  flex-shrink: 0;
}
.lane-bar {
  position: relative;
  flex: 1;
  height: 22px;
  background: #f0f0f0;
  border-radius: 4px;
  overflow: hidden;
}
.lane-bar.emotion {
  height: 18px;
}
.lane-seg {
  position: absolute;
  top: 0;
  height: 100%;
  min-width: 2px;
  cursor: pointer;
  border-right: 1px solid rgba(255, 255, 255, 0.35);
}
.timeline-labels {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}
.legends {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.legend-block {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.legend-title {
  font-size: 12px;
  color: #666;
  width: 28px;
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: #666;
}
.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.tooltip-detail {
  margin-top: 8px;
  padding: 8px 10px;
  background: #f8f9fa;
  border-radius: 8px;
  font-size: 13px;
  color: #333;
}
.tooltip-text {
  color: #666;
  font-size: 12px;
}
.review-tag {
  margin-left: 6px;
  font-size: 11px;
  color: #FF9F0A;
  background: #fff4e5;
  padding: 1px 6px;
  border-radius: 8px;
}
</style>
