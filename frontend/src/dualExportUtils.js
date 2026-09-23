/**
 * 双维编码 CSV 导出（本地）；Excel 走后端 /dual/jobs/{id}/export
 */
import {
  applyBehaviorEdit,
  applyEmotionEdit,
  applyReviewMark,
  applyTextEdit,
  formatTime,
  isBehaviorEdited,
  isEmotionEdited,
  isTextEdited,
  mapDualUnit,
} from './dualConfig.js'

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function csvEscape(value) {
  const s = value == null ? '' : String(value)
  if (/[",\n\r]/.test(s)) {
    return `"${s.replace(/"/g, '""')}"`
  }
  return s
}

export function exportDualCsv({ units, videoName = 'dual_coding' }) {
  const headers = [
    '#',
    '开始时间',
    '结束时间',
    '时长',
    '文本',
    '行为码',
    '行为名称',
    '行为维度',
    '行为判定依据',
    '情绪码',
    '情绪名称',
    '情绪维度',
    '外显情绪线索',
    '置信度',
    '待人工复核',
    '行为是否修改',
    '情绪是否修改',
  ]
  const lines = [headers.join(',')]
  for (const u of units) {
    const row = [
      u.index + 1,
      formatTime(u.start_time),
      formatTime(u.end_time),
      formatTime(u.duration || u.end_time - u.start_time),
      u.text || '',
      u.behavior_code,
      u.behavior_name,
      u.behavior_dim,
      u.behavior_reason,
      u.emotion_code,
      u.emotion_name,
      u.emotion_dim,
      u.emotion_evidence,
      ((u.confidence || 0) * 100).toFixed(1) + '%',
      u.needs_review ? '是' : '否',
      isBehaviorEdited(u) ? '是' : '否',
      isEmotionEdited(u) ? '是' : '否',
    ]
    lines.push(row.map(csvEscape).join(','))
  }
  const csv = '﻿' + lines.join('\r\n')
  const safeName = (videoName || 'dual_coding').replace(/\.[^.]+$/, '') || 'dual_coding'
  downloadBlob(new Blob([csv], { type: 'text/csv;charset=utf-8' }), `${safeName}_双维编码表.csv`)
}

export function buildDualExportPayload({ units, videoName }) {
  return {
    video_name: videoName || '',
    include_matrices: true,
    units: units.map((u) => {
      const mapped = mapDualUnit(u)
      return {
        index: mapped.index,
        start_time: mapped.start_time,
        end_time: mapped.end_time,
        duration: mapped.duration || mapped.end_time - mapped.start_time,
        text: mapped.text || '',
        original_text: mapped.original_text || '',
        behavior_code: mapped.behavior_code,
        behavior_name: mapped.behavior_name || '',
        behavior_dim: mapped.behavior_dim || '',
        behavior_reason: mapped.behavior_reason || '',
        original_behavior_code: mapped.original_behavior_code,
        original_behavior_name: mapped.original_behavior_name || '',
        emotion_code: mapped.emotion_code,
        emotion_name: mapped.emotion_name || '',
        emotion_dim: mapped.emotion_dim || '',
        emotion_evidence: mapped.emotion_evidence || '',
        original_emotion_code: mapped.original_emotion_code,
        original_emotion_name: mapped.original_emotion_name || '',
        confidence: mapped.confidence || 0,
        needs_review: !!mapped.needs_review,
        review_marked: !!mapped.review_marked,
        edited: isBehaviorEdited(mapped) || isEmotionEdited(mapped),
        text_edited: isTextEdited(mapped),
      }
    }),
  }
}

export {
  applyBehaviorEdit,
  applyEmotionEdit,
  applyTextEdit,
  applyReviewMark,
}
