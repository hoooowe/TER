"""
通用情感路径的内存相关配置（环境变量可覆盖）。

目标：只跑 emotion2vec 通用情感时，尽量少常驻大模型，同时
- 情感：默认仍用 emotion2vec_plus_large（保精度）
- ASR：默认 Paraformer-large（句级时间戳准），标点用更小模型
- 人脸 / 自训练多模态：默认不启动预加载
"""
import os


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip()


# 通用情感：emotion2vec | custom（教师多模态，吃内存）
EMOTION_MODEL = _str("EMOTION_MODEL", "emotion2vec")

# 语音情感模型；默认保精度
EMOTION2VEC_MODEL_ID = _str(
    "EMOTION2VEC_MODEL_ID",
    "iic/emotion2vec_plus_large",
)
EMOTION2VEC_MODEL_PATH = _str("EMOTION2VEC_MODEL_PATH", "")
EMOTION2VEC_HUB = _str("EMOTION2VEC_HUB", "ms")

# ASR：paraformer（默认，时间戳稳）| sensevoice（更省内存）
ASR_BACKEND = _str("ASR_BACKEND", "paraformer").lower()

PARAFORMER_MODEL_ID = _str(
    "PARAFORMER_MODEL_ID",
    "iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
)
VAD_MODEL_ID = _str("VAD_MODEL_ID", "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch")

# 标点：
#   default  → 中等词表 zh-cn vocab272727（省内存，分句通常够用）
#   large    → 原 cn-en vocab471067-large（最占内存，分句更“满”）
#   none     → 不加载标点模型，靠时间戳空隙分句
_PUNC_PRESET = _str("PUNC_MODEL", "default").lower()
if _PUNC_PRESET in {"", "default", "medium"}:
    PUNC_MODEL_ID = "iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch"
elif _PUNC_PRESET in {"large", "full"}:
    PUNC_MODEL_ID = "iic/punc_ct-transformer_cn-en-common-vocab471067-large"
elif _PUNC_PRESET in {"none", "off", "null"}:
    PUNC_MODEL_ID = ""
else:
    PUNC_MODEL_ID = _PUNC_PRESET  # 自定义 ModelScope id

# 中等标点不可用时的回退顺序
PUNC_FALLBACK_IDS = [
    PUNC_MODEL_ID,
    "iic/punc_ct-transformer_cn-en-common-vocab471067-large",
    "",
]

SENSEVOICE_MODEL_ID = _str("SENSEVOICE_MODEL_ID", "iic/SenseVoiceSmall")

# 启动时是否预加载 emotion2vec（1–3 人可预热；更省内存可设 0，首次任务时再加载）
PRELOAD_EMOTION = _bool("PRELOAD_EMOTION", True)

# 启动时是否加载人脸模型（批处理通用情感不需要；实时识别首次用到时再加载）
PRELOAD_FACE = _bool("PRELOAD_FACE", False)

# 任务结束后是否释放 ASR 等占用（省内存；1–3 人串行时可设 1）
RELEASE_MODELS_AFTER_JOB = _bool("RELEASE_MODELS_AFTER_JOB", False)

# HuggingFace 镜像
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


def describe() -> str:
    return (
        f"EMOTION_MODEL={EMOTION_MODEL}, "
        f"e2v={EMOTION2VEC_MODEL_ID or EMOTION2VEC_MODEL_PATH}, "
        f"ASR={ASR_BACKEND}, "
        f"punc={PUNC_MODEL_ID or 'none'}, "
        f"preload_emotion={PRELOAD_EMOTION}, "
        f"preload_face={PRELOAD_FACE}, "
        f"release_after_job={RELEASE_MODELS_AFTER_JOB}"
    )
