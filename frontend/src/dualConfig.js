// 教学情绪-行为双维编码配置（论文表1、表3）

export const EMOTION_CODES = [
  { code: 'E1', name: '放松平和', dim: '积极情绪', color: '#34C759' },
  { code: 'E2', name: '愉悦亲和', dim: '积极情绪', color: '#30D158' },
  { code: 'E3', name: '热情振奋', dim: '积极情绪', color: '#FF9F0A' },
  { code: 'U1', name: '客观中性', dim: '中性情绪', color: '#8E8E93' },
  { code: 'N1', name: '紧张拘谨', dim: '消极情绪', color: '#FF453A' },
  { code: 'N2', name: '枯燥敷衍', dim: '消极情绪', color: '#BF5AF2' },
  { code: 'X0', name: '不可观测', dim: '特殊状态', color: '#C7C7CC' },
]

export const BEHAVIOR_CODES = [
  { code: 'B1', name: '知识讲解', dim: '知识讲授', color: '#0A84FF' },
  { code: 'B2', name: '举例说明', dim: '知识讲授', color: '#64D2FF' },
  { code: 'B3', name: '归纳总结', dim: '知识讲授', color: '#5E5CE6' },
  { code: 'B41', name: '全班提问', dim: '教学互动', color: '#FFD60A' },
  { code: 'B42', name: '个体提问', dim: '教学互动', color: '#FF9F0A' },
  { code: 'B43', name: '追问', dim: '教学互动', color: '#FF6B00' },
  { code: 'B5', name: '回应反馈', dim: '教学互动', color: '#32D74B' },
  { code: 'B6', name: '自主作答', dim: '教学互动', color: '#2ED3A7' },
  { code: 'B7', name: '评价激励', dim: '教学互动', color: '#40C8E0' },
  { code: 'B8', name: '刻意停顿', dim: '教学互动', color: '#AC8E68' },
  { code: 'B9', name: '板书书写', dim: '教学操作', color: '#8E8E93' },
  { code: 'B10', name: '操作课件', dim: '教学操作', color: '#636366' },
  { code: 'B11', name: '教学演示', dim: '教学操作', color: '#48484A' },
  { code: 'B12', name: '组织活动', dim: '课堂组织', color: '#FF2D55' },
  { code: 'B13', name: '活动说明', dim: '课堂组织', color: '#FF375F' },
  { code: 'B14', name: '环节过渡', dim: '课堂组织', color: '#D70015' },
  { code: 'B15', name: '授课失误', dim: '失误行为', color: '#BF5AF2' },
]

export const EMOTION_BY_CODE = Object.fromEntries(EMOTION_CODES.map((e) => [e.code, e]))
export const BEHAVIOR_BY_CODE = Object.fromEntries(BEHAVIOR_CODES.map((b) => [b.code, b]))

export function emotionColor(code) {
  return EMOTION_BY_CODE[code]?.color || '#C7C7CC'
}

export function behaviorColor(code) {
  return BEHAVIOR_BY_CODE[code]?.color || '#8E8E93'
}

export function emotionName(code) {
  return EMOTION_BY_CODE[code]?.name || code
}

export function behaviorName(code) {
  return BEHAVIOR_BY_CODE[code]?.name || code
}

export function formatTime(seconds) {
  const s = Number(seconds) || 0
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

export function formatHms(seconds) {
  const total = Math.floor(Number(seconds) || 0)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export function mapDualUnit(unit) {
  return {
    ...unit,
    original_behavior_code: unit.original_behavior_code || unit.behavior_code,
    original_emotion_code: unit.original_emotion_code || unit.emotion_code,
    original_behavior_name: unit.original_behavior_name || unit.behavior_name,
    original_emotion_name: unit.original_emotion_name || unit.emotion_name,
    original_text: unit.original_text ?? unit.text ?? '',
  }
}

export function isBehaviorEdited(unit) {
  return unit.behavior_code !== unit.original_behavior_code
}

export function isEmotionEdited(unit) {
  return unit.emotion_code !== unit.original_emotion_code
}

export function isTextEdited(unit) {
  return (unit.text ?? '') !== (unit.original_text ?? '')
}

export function isUnitEdited(unit) {
  return isBehaviorEdited(unit) || isEmotionEdited(unit) || isTextEdited(unit)
}

export function applyBehaviorEdit(unit, code) {
  const meta = BEHAVIOR_BY_CODE[code] || {}
  return {
    ...unit,
    behavior_code: code,
    behavior_name: meta.name || code,
    behavior_dim: meta.dim || '',
  }
}

export function applyEmotionEdit(unit, code) {
  const meta = EMOTION_BY_CODE[code] || {}
  return {
    ...unit,
    emotion_code: code,
    emotion_name: meta.name || code,
    emotion_dim: meta.dim || '',
  }
}

export function applyTextEdit(unit, text) {
  return { ...unit, text: text ?? '' }
}

export function applyReviewMark(unit, marked) {
  return { ...unit, review_marked: !!marked, needs_review: marked ? false : unit.needs_review }
}
