import os
import logging
import warnings
from pathlib import Path
from contextlib import asynccontextmanager

# 抑制第三方库的无关警告
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)

from core import memory_config as memcfg

# memory_config 已设置 HF 镜像；此处兜底
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# 配置日志：确保所有模块的 INFO 日志都能输出到终端
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s",
    force=True,
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from core.auth import get_auth_store

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
STORAGE_DIR = BASE_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
JOBS_DIR = STORAGE_DIR / "jobs"


@asynccontextmanager
async def lifespan(app: FastAPI):
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    initial_password = get_auth_store(STORAGE_DIR).ensure_default_admin()
    if initial_password:
        logger.warning("已创建默认账号 account / %s，请登录后及时修改", initial_password)

    logger.info("Memory profile: %s", memcfg.describe())

    # 人脸模型：通用视频情感批处理不需要；实时识别首次调用时再加载
    if memcfg.PRELOAD_FACE:
        logger.info("预加载面部表情识别模型...")
        try:
            from core.face_recognizer import init_face_recognizer
            init_face_recognizer()
            logger.info("面部表情识别模型加载完成")
        except Exception as e:
            logger.error(f"面部表情识别模型加载失败: {e}")
    else:
        logger.info("跳过人脸模型预加载（实时识别首次使用时再加载）")

    use_custom = memcfg.EMOTION_MODEL == "custom"
    if use_custom:
        logger.info("正在加载自训练多模态情感识别模型（内存占用较高）...")
        try:
            from core.custom_predictor import _get_custom_predictor
            predictor = _get_custom_predictor()
            predictor._ensure_model()
            logger.info("自训练多模态情感识别模型加载完成")
        except Exception as e:
            logger.error(f"自训练模型加载失败: {e}")
            logger.info("回退 emotion2vec（若 PRELOAD_EMOTION 开启）...")
            if memcfg.PRELOAD_EMOTION:
                try:
                    from core.recognizer import _get_predictor
                    _get_predictor()
                    logger.info("emotion2vec 备用模型加载完成")
                except Exception as e2:
                    logger.error(f"emotion2vec 备用模型加载也失败: {e2}")
    elif memcfg.PRELOAD_EMOTION:
        logger.info("预加载语音情感识别模型 (emotion2vec)...")
        try:
            from core.recognizer import _get_predictor
            _get_predictor()
            logger.info("语音情感识别模型加载完成")
        except Exception as e:
            logger.error(f"语音情感识别模型加载失败: {e}")
    else:
        logger.info("跳过 emotion2vec 预加载（首次识别任务时再加载）")

    # ASR 不在启动时加载：首次视频处理再载入，避免空闲占内存
    logger.info("ASR 将在首次视频任务时按需加载（backend=%s, punc=%s）",
                memcfg.ASR_BACKEND, memcfg.PUNC_MODEL_ID or "none")

    yield


app = FastAPI(title="Emotion Web", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
