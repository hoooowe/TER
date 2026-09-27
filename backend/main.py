"""教室情感识别 — 双维编码服务入口。"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path
from contextlib import asynccontextmanager

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s",
    force=True,
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from api.dual_routes import router as dual_router
from core import aliyun_config as acfg
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
        logger.warning("已初始化默认管理员账号，请尽快登录并修改初始密码")

    logger.info("教师情感识别（双维编码）")
    logger.info("模型配置: %s", acfg.describe())
    yield


app = FastAPI(title="Classroom Emotion · Dual Coding", lifespan=lifespan)

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
app.include_router(dual_router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
