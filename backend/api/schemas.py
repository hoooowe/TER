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
