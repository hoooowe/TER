"""导出「教学情绪-行为」标准化双维编码表（Excel）。"""

from __future__ import annotations

import io
from types import SimpleNamespace
from typing import Any, Iterable

from core.coding_framework import (
    BEHAVIOR_CODES,
    BEHAVIOR_ORDER,
    EMOTION_CODES,
    EMOTION_ORDER,
    build_transition_matrices,
    compute_process_metrics,
)


def _format_time(seconds: float) -> str:
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _style_header(ws, headers: list[str], widths: list[int] | None = None):
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    thin = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    ws.freeze_panes = "A2"


def _orig(u: Any, field: str, fallback_field: str, default: str = "") -> str:
    """取 AI 原始值：优先 original_*，缺失时回退到当前值（未修改即原始值）。"""
    val = getattr(u, field, None)
    if val not in (None, ""):
        return val
    return getattr(u, fallback_field, default) or default


# 配色约定：AI 原始结果 = 浅黄，人工修正结果 = 浅蓝
AI_FILL = "FFF2CC"
HUMAN_FILL = "E8F3FF"


def _as_original_units(unit_list: list[Any]) -> list[Any]:
    """把每个编码单元还原成 AI 原始编码，用于计算原始版本的指标与矩阵。"""
    return [
        SimpleNamespace(
            behavior_code=_orig(u, "original_behavior_code", "behavior_code"),
            emotion_code=_orig(u, "original_emotion_code", "emotion_code"),
        )
        for u in unit_list
    ]


def _yn(flag: Any) -> str:
    return "是" if flag else "否"


def _write_edit_log_sheet(wb, unit_list: list[Any]):
    """人工修改对照表：一条修改一行，保留 AI 原始结果与人工修改结果。"""
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    ws = wb.create_sheet("人工修改对照")
    headers = ["#", "开始时间", "结束时间", "修改项", "AI 原始结果", "人工修改结果", "已人工复核"]
    widths = [5, 10, 10, 12, 40, 40, 12]
    _style_header(ws, headers, widths)

    thin = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    orig_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    new_fill = PatternFill(start_color="E8F3FF", end_color="E8F3FF", fill_type="solid")

    row = 2
    for u in unit_list:
        idx = (getattr(u, "index", row - 2) or (row - 2)) + 1
        start = _format_time(getattr(u, "start_time", 0))
        end = _format_time(getattr(u, "end_time", 0))
        reviewed = _yn(getattr(u, "review_marked", False))

        changes = []
        cur_text = getattr(u, "text", "") or ""
        org_text = _orig(u, "original_text", "text")
        if cur_text != org_text:
            changes.append(("文本", org_text, cur_text))

        org_b = _orig(u, "original_behavior_code", "behavior_code")
        if getattr(u, "behavior_code", "") != org_b:
            org_b_name = _orig(u, "original_behavior_name", "behavior_name") or org_b
            cur_b_name = getattr(u, "behavior_name", "") or getattr(u, "behavior_code", "")
            changes.append(("行为编码", f"{org_b} {org_b_name}".strip(), f"{getattr(u, 'behavior_code', '')} {cur_b_name}".strip()))

        org_e = _orig(u, "original_emotion_code", "emotion_code")
        if getattr(u, "emotion_code", "") != org_e:
            org_e_name = _orig(u, "original_emotion_name", "emotion_name") or org_e
            cur_e_name = getattr(u, "emotion_name", "") or getattr(u, "emotion_code", "")
            changes.append(("情绪编码", f"{org_e} {org_e_name}".strip(), f"{getattr(u, 'emotion_code', '')} {cur_e_name}".strip()))

        for kind, original, current in changes:
            values = [idx, start, end, kind, original, current, reviewed]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row, column=col, value=val)
                cell.border = thin
                cell.alignment = Alignment(vertical="center", wrap_text=True)
                if col == 5:
                    cell.fill = orig_fill
                elif col == 6:
                    cell.fill = new_fill
            row += 1

    if row > 2:
        last_col = openpyxl.utils.get_column_letter(len(headers))
        ws.auto_filter.ref = f"A1:{last_col}{row - 1}"
    return row - 2


def _write_matrix_block(ws, start_row: int, title: str, accent: str, matrix, row_order, col_order) -> int:
    """在指定起始行写一个矩阵区块，返回下一个区块可用的起始行。"""
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    thin = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    title_cell = ws.cell(row=start_row, column=1, value=title)
    title_cell.font = Font(bold=True, size=11)
    title_cell.fill = PatternFill(start_color=accent, end_color=accent, fill_type="solid")

    head_row = start_row + 1
    head_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    for col, val in enumerate(["前一状态 \\ 后一状态"] + list(col_order), 1):
        cell = ws.cell(row=head_row, column=col, value=val)
        cell.fill = head_fill
        cell.font = Font(color="FFFFFF", bold=True, size=10)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin

    body_fill = PatternFill(start_color=accent, end_color=accent, fill_type="solid")
    for i, r in enumerate(row_order, head_row + 1):
        head_cell = ws.cell(row=i, column=1, value=r)
        head_cell.font = Font(bold=True, size=10)
        head_cell.border = thin
        head_cell.fill = PatternFill(start_color="F2F2F7", end_color="F2F2F7", fill_type="solid")
        for j, c in enumerate(col_order, 2):
            cell = ws.cell(row=i, column=j, value=matrix.get(r, {}).get(c, 0))
            cell.border = thin
            cell.alignment = Alignment(horizontal="center")
            if cell.value:
                cell.fill = body_fill

    # 数据结束行 + 1（留一个空行）
    return head_row + len(row_order) + 2


def _write_matrix_sheet(
    wb,
    title: str,
    ai_matrix: dict[str, dict[str, int]],
    human_matrix: dict[str, dict[str, int]],
    row_order: list[str],
    col_order: list[str],
):
    """一个 sheet 上下两块：AI 原始矩阵 + 人工修正矩阵，方便直接对照。"""
    import openpyxl

    ws = wb.create_sheet(title)
    ws.column_dimensions["A"].width = 16
    for j in range(len(col_order)):
        ws.column_dimensions[openpyxl.utils.get_column_letter(j + 2)].width = 8
    nxt = _write_matrix_block(ws, 1, "AI 原始结果", AI_FILL, ai_matrix, row_order, col_order)
    _write_matrix_block(ws, nxt, "人工修正结果", HUMAN_FILL, human_matrix, row_order, col_order)
    ws.freeze_panes = "B3"


def build_dual_excel_bytes(
    units: Iterable[Any],
    *,
    video_name: str = "",
    include_matrices: bool = True,
) -> bytes:
    """
    生成标准化双维编码表 Excel。

    Sheet1 双维编码表：# / 开始 / 结束 / 时长 / AI原始文本 / 人工修正文本 / 文本是否修改 /
                    AI原始行为码 / AI原始行为名称 / 人工行为码 / 人工行为名称 / 行为维度 /
                    行为判定依据 / 行为是否修改 /
                    AI原始情绪码 / AI原始情绪名称 / 人工情绪码 / 人工情绪名称 / 情绪维度 /
                    外显情绪线索 / 情绪是否修改 /
                    置信度 / 待人工复核 / 已人工复核
    Sheet2 编码手册
    Sheet3 过程指标：每个指标同时给出「AI 原始」与「人工修正」及差值
    Sheet4 人工修改对照（有修改记录时才有内容）
    Sheet5-7 矩阵（可选）：每个 sheet 内上下两块，AI 原始矩阵 + 人工修正矩阵
    """
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    unit_list = list(units)
    wb = openpyxl.Workbook()

    # ---------- Sheet1 双维编码表 ----------
    ws = wb.active
    ws.title = "双维编码表"
    headers = [
        "#", "开始时间", "结束时间", "时长",
        "AI 原始文本", "人工修正文本", "文本是否修改",
        "AI 原始行为码", "AI 原始行为名称",
        "人工行为码", "人工行为名称", "行为维度", "行为判定依据", "行为是否修改",
        "AI 原始情绪码", "AI 原始情绪名称",
        "人工情绪码", "人工情绪名称", "情绪维度", "外显情绪线索", "情绪是否修改",
        "置信度", "待人工复核", "已人工复核",
    ]
    widths = [
        5, 10, 10, 8,
        36, 36, 10,
        11, 14,
        11, 14, 12, 28, 10,
        11, 14,
        11, 14, 12, 28, 10,
        8, 10, 10,
    ]
    _style_header(ws, headers, widths)
    col_of = {h: i + 1 for i, h in enumerate(headers)}

    review_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    edited_fill = PatternFill(start_color="E8F3FF", end_color="E8F3FF", fill_type="solid")
    thin = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    for row_idx, u in enumerate(unit_list, 2):
        cur_text = getattr(u, "text", "") or ""
        org_text = _orig(u, "original_text", "text")
        text_edited = cur_text != org_text

        org_b_code = _orig(u, "original_behavior_code", "behavior_code")
        cur_b_code = getattr(u, "behavior_code", "")
        b_edited = cur_b_code != org_b_code

        org_e_code = _orig(u, "original_emotion_code", "emotion_code")
        cur_e_code = getattr(u, "emotion_code", "")
        e_edited = cur_e_code != org_e_code

        needs_review = bool(getattr(u, "needs_review", False))
        reviewed = bool(getattr(u, "review_marked", False))

        values = [
            getattr(u, "index", row_idx - 2) + 1 if hasattr(u, "index") else row_idx - 1,
            _format_time(getattr(u, "start_time", 0)),
            _format_time(getattr(u, "end_time", 0)),
            _format_time(getattr(u, "duration", 0) or (getattr(u, "end_time", 0) - getattr(u, "start_time", 0))),
            org_text,
            cur_text,
            _yn(text_edited),
            org_b_code,
            _orig(u, "original_behavior_name", "behavior_name") or org_b_code,
            cur_b_code,
            getattr(u, "behavior_name", ""),
            getattr(u, "behavior_dim", ""),
            getattr(u, "behavior_reason", ""),
            _yn(b_edited),
            org_e_code,
            _orig(u, "original_emotion_name", "emotion_name") or org_e_code,
            cur_e_code,
            getattr(u, "emotion_name", ""),
            getattr(u, "emotion_dim", ""),
            getattr(u, "emotion_evidence", ""),
            _yn(e_edited),
            round(float(getattr(u, "confidence", 0) or 0), 4),
            _yn(needs_review),
            _yn(reviewed),
        ]
        edited_cols = set()
        if text_edited:
            edited_cols |= {col_of["人工修正文本"], col_of["文本是否修改"]}
        if b_edited:
            edited_cols |= {
                col_of["人工行为码"], col_of["人工行为名称"], col_of["行为是否修改"],
            }
        if e_edited:
            edited_cols |= {
                col_of["人工情绪码"], col_of["人工情绪名称"], col_of["情绪是否修改"],
            }

        for col, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.border = thin
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            if col in edited_cols:
                cell.fill = edited_fill
            elif needs_review:
                cell.fill = review_fill

    if unit_list:
        last_col = openpyxl.utils.get_column_letter(len(headers))
        ws.auto_filter.ref = f"A1:{last_col}{len(unit_list) + 1}"

    # ---------- Sheet2 编码手册 ----------
    ws2 = wb.create_sheet("编码手册")
    _style_header(ws2, ["维度", "编码", "名称", "描述"], [12, 8, 14, 60])
    r = 2
    for e in EMOTION_CODES:
        ws2.cell(row=r, column=1, value="情绪-" + e["dim"])
        ws2.cell(row=r, column=2, value=e["code"])
        ws2.cell(row=r, column=3, value=e["name"])
        ws2.cell(row=r, column=4, value=e["description"])
        r += 1
    for b in BEHAVIOR_CODES:
        ws2.cell(row=r, column=1, value="行为-" + b["dim"])
        ws2.cell(row=r, column=2, value=b["code"])
        ws2.cell(row=r, column=3, value=b["name"])
        ws2.cell(row=r, column=4, value=b["description"])
        r += 1

    # ---------- Sheet3 过程指标（AI 原始 vs 人工修正） ----------
    ai_metrics = compute_process_metrics(_as_original_units(unit_list))
    hu_metrics = compute_process_metrics(unit_list)
    ws3 = wb.create_sheet("过程指标")
    _style_header(
        ws3,
        ["指标缩写", "中文名称", "AI 原始", "人工修正", "差值", "含义"],
        [12, 18, 12, 12, 10, 50],
    )
    ai_f = PatternFill(start_color=AI_FILL, end_color=AI_FILL, fill_type="solid")
    hu_f = PatternFill(start_color=HUMAN_FILL, end_color=HUMAN_FILL, fill_type="solid")
    diff_f = PatternFill(start_color="FFE0E0", end_color="FFE0E0", fill_type="solid")

    metric_rows = [
        ("KPBR", "知识呈现行为占比", "知识讲解、举例说明、归纳总结等占全部教学行为的比例"),
        ("IIBR", "教学互动行为占比", "提问、反馈、评价等互动行为占全部教学行为的比例"),
        ("IOBR", "教学操作行为占比", "板书、课件操作、教学演示等占全部教学行为的比例"),
        ("COBR", "课堂组织行为占比", "活动组织、活动说明、环节过渡等占全部教学行为的比例"),
        ("TEOR", "失误行为发生率", "授课失误行为占全部教学行为事件的比例"),
        ("PER", "积极情绪出现率", "积极情绪（E1-E3）占全部情绪编码事件的比例"),
        ("NER", "中性情绪出现率", "中性情绪（U1）占全部情绪编码事件的比例"),
        ("NGR", "消极情绪出现率", "消极情绪（N1-N2）占全部情绪编码事件的比例"),
    ]
    for i, (key, name, desc) in enumerate(metric_rows, 2):
        ai_v = round(float(ai_metrics.get(key, 0) or 0), 4)
        hu_v = round(float(hu_metrics.get(key, 0) or 0), 4)
        diff = round(hu_v - ai_v, 4)
        ws3.cell(row=i, column=1, value=key)
        ws3.cell(row=i, column=2, value=name)
        ws3.cell(row=i, column=3, value=ai_v).fill = ai_f
        ws3.cell(row=i, column=4, value=hu_v).fill = hu_f
        d_cell = ws3.cell(row=i, column=5, value=diff)
        if diff:
            d_cell.fill = diff_f
        ws3.cell(row=i, column=6, value=desc)

    note_row = len(metric_rows) + 3
    ws3.cell(
        row=note_row,
        column=1,
        value="AI 原始 = 模型自动编码结果；人工修正 = 人工复核修改后的最终结果；差值 = 人工修正 − AI 原始。",
    ).font = Font(italic=True, size=10, color="888888")

    # ---------- Sheet4 人工修改对照（仅在存在修改时生成） ----------
    _write_edit_log_sheet(wb, unit_list)

    if include_matrices:
        hu_mats = build_transition_matrices(unit_list)
        ai_mats = build_transition_matrices(_as_original_units(unit_list))
        _write_matrix_sheet(
            wb, "行为连接矩阵",
            ai_mats["behavior_transition"], hu_mats["behavior_transition"],
            BEHAVIOR_ORDER, BEHAVIOR_ORDER,
        )
        _write_matrix_sheet(
            wb, "情绪转换矩阵",
            ai_mats["emotion_transition"], hu_mats["emotion_transition"],
            EMOTION_ORDER, EMOTION_ORDER,
        )
        # 共现：行=情绪，列=行为
        _write_matrix_sheet(
            wb, "行为情绪共现矩阵",
            ai_mats["emotion_behavior_cooccurrence"], hu_mats["emotion_behavior_cooccurrence"],
            EMOTION_ORDER, BEHAVIOR_ORDER,
        )

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
