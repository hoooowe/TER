"""教室情感识别 — 教学情绪-行为双维编码数据模型。"""

from pydantic import BaseModel
from typing import Optional


class DualCodingUnit(BaseModel):
    """教学情绪-行为双维编码单元（一个片段 = 一个行为码 + 一个情绪码）。"""
    index: int
    start_time: float
    end_time: float
    duration: float
    text: str = ""
    behavior_code: str
    behavior_name: str = ""
    behavior_dim: str = ""
    behavior_reason: str = ""
    emotion_code: str
    emotion_name: str = ""
    emotion_dim: str = ""
    emotion_evidence: str = ""
    confidence: float = 0.0
    needs_review: bool = False
    status: str = "ok"
    source: str = "vl"
    original_behavior_code: str = ""
    original_emotion_code: str = ""
    original_behavior_name: str = ""
    original_emotion_name: str = ""
    original_text: str = ""
    edited: bool = False
    text_edited: bool = False
    review_marked: bool = False


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
    status: str
    progress: float = 0.0
    message: str = ""
    event: str = "progress"
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
    job_type: str = "dual"
