from pydantic import BaseModel
from typing import Optional


class SegmentResult(BaseModel):
    index: int
    start_time: float
    end_time: float
    duration: float
    text: str
    label: int  # 0-3
    label_name: str
    label_name_cn: str
    confidence: float
    emotion2vec_label: int
    emotion2vec_label_name: str
    status: str = "ok"  # ok / error


class JobStatus(BaseModel):
    job_id: str
    status: str  # pending / processing / done / failed
    progress: float = 0.0  # 0.0 ~ 1.0
    message: str = ""
    # 逐段推送扩展字段
    event: str = "progress"  # progress | segment | snapshot | done | failed
    segments_done: int = 0
    segments_total: int = 0
    segment: Optional[SegmentResult] = None
    segments: Optional[list[SegmentResult]] = None
    video_name: str = ""
    total_duration: float = 0.0
    complete: bool = False


class JobResult(BaseModel):
    job_id: str
    video_name: str
    total_duration: float
    segments: list[SegmentResult]
    complete: bool = True


class ExportSegment(BaseModel):
    """前端可编辑后的导出数据行"""
    index: int
    start_time: float
    end_time: float
    duration: float
    text: str = ""
    original_text: str = ""
    # 识别结果（原始）
    original_label: int
    original_label_name: str = ""
    original_emotion2vec_label: int
    original_emotion2vec_label_name: str = ""
    # 最终（可能已编辑）
    label: int
    label_name_cn: str = ""
    emotion2vec_label: int
    emotion2vec_label_name: str = ""
    confidence: float = 0.0
    edited: bool = False  # 情感是否修改
    text_edited: bool = False  # ASR 文本是否修改


class ExportRequest(BaseModel):
    video_name: str = ""
    label_mode: str = "e2v"  # e2v | teacher
    segments: list[ExportSegment]


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthUserOut(BaseModel):
    user_id: str
    username: str


class HistoryItem(BaseModel):
    job_id: str
    video_name: str
    status: str
    message: str = ""
    created_at: str = ""
    total_duration: float = 0.0
    segment_count: int = 0
    job_type: str = "emotion"  # emotion | dual


class DualCodingUnit(BaseModel):
    """教学情绪-行为双维编码单元（一个片段 = 一个行为码 + 一个情绪码）。"""
    index: int
    start_time: float
    end_time: float
    duration: float
    text: str = ""
    # 行为
    behavior_code: str
    behavior_name: str = ""
    behavior_dim: str = ""
    behavior_reason: str = ""
    # 情绪（可观察外显）
    emotion_code: str
    emotion_name: str = ""
    emotion_dim: str = ""
    emotion_evidence: str = ""
    # 置信与复核
    confidence: float = 0.0
    needs_review: bool = False
    status: str = "ok"
    source: str = "vl"
    # 识别原值（人工复核编辑后仍可追溯）
    original_behavior_code: str = ""
    original_emotion_code: str = ""
    original_behavior_name: str = ""
    original_emotion_name: str = ""
    original_text: str = ""
    edited: bool = False
    text_edited: bool = False
    review_marked: bool = False  # 人工标记已复核


class DualCodingResult(BaseModel):
    job_id: str
    video_name: str
    total_duration: float
    units: list[DualCodingUnit]
    complete: bool = True
    summary: dict = {}
    sequences: dict = {}


class DualJobStatus(BaseModel):
    job_id: str
    status: str  # pending / processing / done / failed
    progress: float = 0.0
    message: str = ""
    event: str = "progress"  # progress | unit | snapshot | done | failed
    units_done: int = 0
    units_total: int = 0
    unit: Optional[DualCodingUnit] = None
    units: Optional[list[DualCodingUnit]] = None
    video_name: str = ""
    total_duration: float = 0.0
    complete: bool = False


class DualExportUnit(BaseModel):
    index: int
    start_time: float
    end_time: float
    duration: float
    text: str = ""
    original_text: str = ""
    behavior_code: str
    behavior_name: str = ""
    behavior_dim: str = ""
    behavior_reason: str = ""
    original_behavior_code: str = ""
    original_behavior_name: str = ""
    emotion_code: str
    emotion_name: str = ""
    emotion_dim: str = ""
    emotion_evidence: str = ""
    original_emotion_code: str = ""
    original_emotion_name: str = ""
    confidence: float = 0.0
    needs_review: bool = False
    review_marked: bool = False
    edited: bool = False
    text_edited: bool = False


class DualExportRequest(BaseModel):
    video_name: str = ""
    units: list[DualExportUnit]
    include_matrices: bool = True
