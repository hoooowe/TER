import {
  ENABLE_TEACHER_EMOTION,
  getLabel,
  getLabelName,
  getOriginalLabel,
  getOriginalLabelName,
  getOriginalText,
  isLabelEdited,
  isTextEdited,
  formatTime,
} from './emotionConfig.js'

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

/**
 * 按当前编辑后的情感与识别文本导出 CSV
 * 当前默认只导出通用 emotion2vec 9 类，不含教师情感列
 */
export function exportCsv({ segments, videoName = 'result', labelMode = 'e2v' }) {
  const mode = ENABLE_TEACHER_EMOTION ? labelMode : 'e2v'
  const isTeacher = mode === 'teacher'
  const headers = [
    '#',
    '开始时间',
    '结束时间',
    '时长',
    '识别文本',
    '最终文本',
    '文本是否修改',
    isTeacher ? '识别-教师标签名' : '识别-情感标签名',
    isTeacher ? '最终-教师标签名' : '最终-情感标签名',
    '识别标签值',
    '最终标签值',
    '置信度',
    '情感是否修改',
  ]

  const lines = [headers.join(',')]
  for (const seg of segments) {
    const row = [
      seg.index + 1,
      formatTime(seg.start_time),
      formatTime(seg.end_time),
      formatTime(seg.duration),
      getOriginalText(seg),
      seg.text || '',
      isTextEdited(seg) ? '是' : '否',
      getOriginalLabelName(seg, mode),
      getLabelName(seg, mode),
      getOriginalLabel(seg, mode),
      getLabel(seg, mode),
      ((seg.confidence || 0) * 100).toFixed(1) + '%',
      isLabelEdited(seg, mode) ? '是' : '否',
    ]
    lines.push(row.map(csvEscape).join(','))
  }

  // UTF-8 BOM，Excel 打开中文不乱码
  const csv = '﻿' + lines.join('\r\n')
  const safeName = (videoName || 'result').replace(/\.[^.]+$/, '') || 'result'
  downloadBlob(new Blob([csv], { type: 'text/csv;charset=utf-8' }), `${safeName}_emotions.csv`)
}

/**
 * 用编辑后的情感与识别文本请求后端导出 Excel
 * 当前强制通用 emotion2vec，不导出教师情感列
 */
export async function exportExcel({ jobId, segments, videoName, labelMode, requestFn }) {
  const mode = ENABLE_TEACHER_EMOTION ? (labelMode || 'e2v') : 'e2v'
  const payload = {
    video_name: videoName || '',
    label_mode: mode,
    // 后端按通用情感导出；文本与情感均使用前端编辑后的最终值
    segments: segments.map((seg) => ({
      index: seg.index,
      start_time: seg.start_time,
      end_time: seg.end_time,
      duration: seg.duration,
      original_text: getOriginalText(seg),
      text: seg.text || '',
      original_label: getOriginalLabel(seg, 'teacher'),
      original_label_name: getOriginalLabelName(seg, 'teacher'),
      original_emotion2vec_label: getOriginalLabel(seg, 'e2v'),
      original_emotion2vec_label_name: getOriginalLabelName(seg, 'e2v'),
      label: seg.label,
      label_name_cn: seg.label_name_cn || '',
      emotion2vec_label: seg.emotion2vec_label,
      emotion2vec_label_name: seg.emotion2vec_label_name || '',
      confidence: seg.confidence || 0,
      edited: isLabelEdited(seg, mode),
      text_edited: isTextEdited(seg),
    })),
  }

  const res = await requestFn(jobId, payload)
  const blob = new Blob([res.data], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  const safeName = (videoName || 'result').replace(/\.[^.]+$/, '') || 'result'
  downloadBlob(blob, `${safeName}_emotions.xlsx`)
}
