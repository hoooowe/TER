"""
教学情绪-行为双维编码框架（依据论文第三章）。

情绪：V-A 模型离散化 → 积极 E1-E3 / 中性 U1 / 消极 N1-N2 / 特殊 X0
行为：CTBAS 功能化重构 → 知识讲授 / 教学互动 / 教学操作 / 课堂组织 / 授课失误
"""

from __future__ import annotations

from typing import Any


# ==================== 情绪编码 ====================

EMOTION_CODES: list[dict[str, str]] = [
    {
        "code": "E1",
        "name": "放松平和",
        "dim": "积极情绪",
        "description": "面部表情自然舒展，语气平稳柔和，身体姿态放松，动作连贯流畅，整体呈现稳定、从容的教学演示状态。",
    },
    {
        "code": "E2",
        "name": "愉悦亲和",
        "dim": "积极情绪",
        "description": "面带微笑，语调出现变化，语气亲切柔和，身体姿态自然，伴随与教学表达同步的手势或姿态变化。",
    },
    {
        "code": "E3",
        "name": "热情振奋",
        "dim": "积极情绪",
        "description": "教学演示过程中表情变化丰富，语调与语速随教学内容发生变化，并通过重音突出关键信息；伴随丰富的手势或大幅度的身体动作。",
    },
    {
        "code": "U1",
        "name": "客观中性",
        "dim": "中性情绪",
        "description": "面部表情保持平静，无明显情绪表达；语音主要用于信息传递，语调和语气无情感变化，身体动作主要服务于教学任务完成。",
    },
    {
        "code": "N1",
        "name": "紧张拘谨",
        "dim": "消极情绪",
        "description": "面部出现紧绷、皱眉、抿嘴等不自然表情，语音出现停顿、重复表达；身体动作拘谨僵硬，持续避免与模拟对象进行视觉交流。",
    },
    {
        "code": "N2",
        "name": "枯燥敷衍",
        "dim": "消极情绪",
        "description": "面部表情长时间保持单一状态；语音保持单调输出，缺少情感变化；教学表达主要表现为机械讲述，缺少面向模拟对象的情感表达。",
    },
    {
        "code": "X0",
        "name": "不可观测状态",
        "dim": "特殊状态",
        "description": "在微格教学过程中，教师长时间背对镜头板书、面部被遮挡、声音缺失或关键情绪线索无法同时获取。",
    },
]

# ==================== 行为编码 ====================

BEHAVIOR_CODES: list[dict[str, str]] = [
    {
        "code": "B1",
        "name": "知识讲解",
        "dim": "知识讲授",
        "description": "针对教学内容中的知识点、概念、原理等进行直接阐释与说明",
    },
    {
        "code": "B2",
        "name": "举例说明",
        "dim": "知识讲授",
        "description": "通过实例、案例、类比或故事等方式辅助知识理解",
    },
    {
        "code": "B3",
        "name": "归纳总结",
        "dim": "知识讲授",
        "description": "对已呈现的教学内容进行提炼概括，总结重点、规律或知识结构",
    },
    {
        "code": "B41",
        "name": "全班提问",
        "dim": "教学互动",
        "description": "面向模拟课堂中的整体学习对象提出问题",
    },
    {
        "code": "B42",
        "name": "个体提问",
        "dim": "教学互动",
        "description": "针对特定模拟对象提出问题，要求其回答或表达观点",
    },
    {
        "code": "B43",
        "name": "追问",
        "dim": "教学互动",
        "description": "基于预设回答进一步提出问题，引导解释、补充或深入思考",
    },
    {
        "code": "B5",
        "name": "回应反馈",
        "dim": "教学互动",
        "description": "针对模拟回答、预设学生反应或教学互动情境进行回应、补充、纠正或延伸说明",
    },
    {
        "code": "B6",
        "name": "自主作答",
        "dim": "教学互动",
        "description": "提出问题后未设置等待过程，直接进行答案呈现或解释说明",
    },
    {
        "code": "B7",
        "name": "评价激励",
        "dim": "教学互动",
        "description": "对预设学生学习表现、回答结果或课堂表现进行评价、肯定、鼓励或提出改进建议",
    },
    {
        "code": "B8",
        "name": "刻意停顿",
        "dim": "教学互动",
        "description": "在模拟教学表达过程中主动停止语言输出，形成等待、思考或强调教学内容的时间间隔。",
    },
    {
        "code": "B9",
        "name": "板书书写",
        "dim": "教学操作",
        "description": "在黑板、白板等媒介上书写文字、公式、图示或呈现知识结构",
    },
    {
        "code": "B10",
        "name": "操作课件",
        "dim": "教学操作",
        "description": "操控PPT、动画、视频等数字化教学资源辅助教学内容呈现",
    },
    {
        "code": "B11",
        "name": "教学演示",
        "dim": "教学操作",
        "description": "通过实验操作、实物展示、模型呈现或动作示范等展示教学内容",
    },
    {
        "code": "B12",
        "name": "组织活动",
        "dim": "课堂组织",
        "description": "设计并组织讨论、练习、探究、游戏等模拟教学活动",
    },
    {
        "code": "B13",
        "name": "活动说明",
        "dim": "课堂组织",
        "description": "对教学活动的目标、规则、要求、实施流程及注意事项进行讲解",
    },
    {
        "code": "B14",
        "name": "环节过渡",
        "dim": "课堂组织",
        "description": "衔接不同教学内容或活动环节，实现模拟教学流程转换",
    },
    {
        "code": "B15",
        "name": "授课失误",
        "dim": "失误行为",
        "description": "在模拟授课过程中出现口误、知识表达错误、操作失误或非计划性中断等异常情况",
    },
]

EMOTION_BY_CODE = {e["code"]: e for e in EMOTION_CODES}
BEHAVIOR_BY_CODE = {b["code"]: b for b in BEHAVIOR_CODES}

BEHAVIOR_ORDER = [b["code"] for b in BEHAVIOR_CODES]
EMOTION_ORDER = [e["code"] for e in EMOTION_CODES]

# 过程指标分组（表8）
BEHAVIOR_METRIC_GROUPS = {
    "KPBR": ["B1", "B2", "B3"],          # 知识呈现行为占比
    "IIBR": ["B41", "B42", "B43", "B5", "B6", "B7", "B8"],  # 教学互动行为占比
    "IOBR": ["B9", "B10", "B11"],         # 教学操作行为占比
    "COBR": ["B12", "B13", "B14"],        # 课堂组织行为占比
    "TEOR": ["B15"],                       # 失误行为发生率
}

EMOTION_METRIC_GROUPS = {
    "PER": ["E1", "E2", "E3"],  # 积极情绪出现率
    "NER": ["U1"],              # 中性情绪出现率
    "NGR": ["N1", "N2"],        # 消极情绪出现率
}


def codebook() -> dict[str, Any]:
    return {
        "emotions": EMOTION_CODES,
        "behaviors": BEHAVIOR_CODES,
        "emotion_order": EMOTION_ORDER,
        "behavior_order": BEHAVIOR_ORDER,
    }


def emotion_info(code: str) -> dict[str, str]:
    return EMOTION_BY_CODE.get(code, {"code": code, "name": code, "dim": "", "description": ""})


def behavior_info(code: str) -> dict[str, str]:
    return BEHAVIOR_BY_CODE.get(code, {"code": code, "name": code, "dim": "", "description": ""})


def build_coding_prompt(
    text: str,
    context_prev: str = "",
    context_next: str = "",
    has_visual: bool = True,
) -> str:
    """构建给 Qwen-VL 的双维编码提示词。"""
    emotion_block = "\n".join(
        f"- {e['code']} {e['name']}（{e['dim']}）：{e['description']}" for e in EMOTION_CODES
    )
    behavior_block = "\n".join(
        f"- {b['code']} {b['name']}（{b['dim']}）：{b['description']}" for b in BEHAVIOR_CODES
    )

    visual_hint = (
        "所附图片为该片段视频抽帧，须综合观察面部表情、目光、身体姿态、手势、动作幅度、是否背对镜头/板书等外显线索。"
        if has_visual
        else "本片段无可用画面，请仅依据有限线索判断；关键情绪线索缺失时必须输出 X0。"
    )

    return f"""你是微格教学（模拟教学）视频的双维编码员。请对该教学片段输出一组「教学行为编码 + 教学情绪编码」。

## 任务目标
把连续教学过程切分为编码单元：一个片段 = 一个主要行为编码 + 一个可观察情绪编码。
本系统用于研究过程表征，不评价教学能力，不猜测教师内心真实情绪。

## 教学情绪编码（只识别可观察外显状态）
{emotion_block}

情绪判定流程：外显线索识别 → 效价判断（积极/中性/消极）→ 激活水平判断 → 映射具体类别。
多线索一致性原则：至少两类独立外显线索（如面部+语音语调、姿态+语音）共同支持同一情绪时才可编码；线索不足或互相矛盾时倾向输出 X0 或调低置信度。
禁止仅根据语言语义推断“内心情绪”。
{visual_hint}

## 教学行为编码（以教学功能判断，不能仅凭关键词）
{behavior_block}

行为判定流程：教学事件识别 → 教学功能判断 → 行为类别匹配。
教学功能优先原则：同一时间段出现多个行为时，按该时段主要教学功能编码（例如边讲解边板书且板书是辅助，则编 B1；板书本身成为主要信息载体，则编 B9）。
微格教学中互动常为模拟提问/自问自答，不以“是否有真实学生回应”否定互动行为。
排他性：同一时间只输出一个主要行为编码。

## 本片段信息
- 当前转写文本：{text or "（无有效语音）"}
- 上文：{context_prev or "（无）"}
- 下文：{context_next or "（无）"}

## 输出要求
只输出一个 JSON 对象，不要其它解释文字：
{{
  "behavior_code": "B1|B2|...|B15",
  "behavior_reason": "说明该时段主要教学功能及为何匹配该行为码",
  "emotion_code": "E1|E2|E3|U1|N1|N2|X0",
  "emotion_evidence": "至少两条外显线索依据，用分号分隔；若 X0 则写明不可观测原因",
  "confidence": 0.0到1.0,
  "needs_review": true或false
}}
confidence 表示对该双维编码的综合把握；把握不足、线索冲突、边界模糊时 needs_review 为 true。
"""


def parse_vl_json(raw: str) -> dict[str, Any]:
    """从模型输出中解析 JSON，容忍代码块包裹与前后杂讯。"""
    import json
    import re

    if not raw:
        return {}
    text = raw.strip()
    # 剥离 ```json ... ```
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    # 取第一个 {...}
    brace = re.search(r"\{[\s\S]*\}", text)
    if brace:
        text = brace.group(0)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def normalize_codes(
    behavior_code: str,
    emotion_code: str,
    *,
    behavior_reason: str = "",
    emotion_evidence: str = "",
    confidence: float = 0.0,
    needs_review: bool | None = None,
    confidence_threshold: float = 0.7,
) -> dict[str, Any]:
    """校验并规范化模型输出。"""
    b = (behavior_code or "").strip().upper()
    e = (emotion_code or "").strip().upper()

    # 兼容 B4 / B4x 等
    if b in {"B4", "B40"}:
        b = "B41"
    if b not in BEHAVIOR_BY_CODE:
        # 尝试去掉空格
        b2 = b.replace(" ", "")
        b = b2 if b2 in BEHAVIOR_BY_CODE else "B1"
    if e not in EMOTION_BY_CODE:
        e2 = e.replace(" ", "")
        e = e2 if e2 in EMOTION_BY_CODE else "X0"

    try:
        conf = float(confidence)
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))

    review = bool(needs_review) if needs_review is not None else conf < confidence_threshold
    if conf < confidence_threshold:
        review = True

    binfo = behavior_info(b)
    einfo = emotion_info(e)
    return {
        "behavior_code": b,
        "behavior_name": binfo["name"],
        "behavior_dim": binfo["dim"],
        "behavior_reason": (behavior_reason or "").strip(),
        "emotion_code": e,
        "emotion_name": einfo["name"],
        "emotion_dim": einfo["dim"],
        "emotion_evidence": (emotion_evidence or "").strip(),
        "confidence": round(conf, 4),
        "needs_review": review,
    }


def compute_process_metrics(units: list[Any]) -> dict[str, float]:
    """计算表8中的行为/情绪过程指标（按编码事件数占比）。"""
    total_b = 0
    total_e = 0
    b_counts: dict[str, int] = {c: 0 for c in BEHAVIOR_ORDER}
    e_counts: dict[str, int] = {c: 0 for c in EMOTION_ORDER}

    for u in units:
        bc = getattr(u, "behavior_code", None) or (u.get("behavior_code") if isinstance(u, dict) else None)
        ec = getattr(u, "emotion_code", None) or (u.get("emotion_code") if isinstance(u, dict) else None)
        if bc in b_counts:
            b_counts[bc] += 1
            total_b += 1
        if ec in e_counts:
            e_counts[ec] += 1
            total_e += 1

    def ratio(codes: list[str], total: int, counts: dict[str, int]) -> float:
        if total <= 0:
            return 0.0
        return round(sum(counts.get(c, 0) for c in codes) / total, 4)

    metrics: dict[str, float] = {}
    for key, codes in BEHAVIOR_METRIC_GROUPS.items():
        metrics[key] = ratio(codes, total_b, b_counts)
    for key, codes in EMOTION_METRIC_GROUPS.items():
        metrics[key] = ratio(codes, total_e, e_counts)
    metrics["behavior_events"] = float(total_b)
    metrics["emotion_events"] = float(total_e)
    return metrics


def build_transition_matrices(units: list[Any]) -> dict[str, Any]:
    """构建行为连接矩阵、情绪转换矩阵、行为-情绪共现矩阵（相邻序对计数）。"""
    b_seq: list[str] = []
    e_seq: list[str] = []
    pairs: list[tuple[str, str]] = []

    for u in units:
        bc = getattr(u, "behavior_code", None) or (u.get("behavior_code") if isinstance(u, dict) else None)
        ec = getattr(u, "emotion_code", None) or (u.get("emotion_code") if isinstance(u, dict) else None)
        if bc:
            b_seq.append(bc)
        if ec:
            e_seq.append(ec)
        if bc and ec:
            pairs.append((bc, ec))

    def count_transitions(seq: list[str], order: list[str]) -> dict[str, dict[str, int]]:
        mat = {a: {b: 0 for b in order} for a in order}
        for i in range(len(seq) - 1):
            a, b = seq[i], seq[i + 1]
            if a in mat and b in mat[a]:
                mat[a][b] += 1
        return mat

    def count_cooccur(pairs_: list[tuple[str, str]], b_order: list[str], e_order: list[str]) -> dict[str, dict[str, int]]:
        # 行=情绪，列=行为（论文表7）
        mat = {e: {b: 0 for b in b_order} for e in e_order}
        for b, e in pairs_:
            if e in mat and b in mat[e]:
                mat[e][b] += 1
        return mat

    return {
        "behavior_transition": count_transitions(b_seq, BEHAVIOR_ORDER),
        "emotion_transition": count_transitions(e_seq, EMOTION_ORDER),
        "emotion_behavior_cooccurrence": count_cooccur(pairs, BEHAVIOR_ORDER, EMOTION_ORDER),
        "behavior_sequence": b_seq,
        "emotion_sequence": e_seq,
    }
