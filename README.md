# TER

**Teacher Emotion Recognition** — 教师情感识别系统。

上传教学视频，自动按句子切分，FunASR Paraformer 做中文语音识别，emotion2vec+ 做情感分类，在时间轴与结果表格中展示，并支持历史回看与导出。

仓库：`hoooowe/ter`

## 功能

- 账号登录（HMAC Cookie + PBKDF2 密码；首次启动自动创建默认管理员）
- 上传教学视频（MP4 / AVI / MOV / MKV / FLV / WMV）
- FunASR Paraformer 中文 ASR（VAD + 标点），按句号/问号/感叹号自动切分
- emotion2vec+ 情感识别（默认 9 类；可选教师场景 4 类）
- SSE 实时进度：每识别完一段立即推送到前端
- 时间轴可视化、视频播放器、结果表格（可筛选、可编辑文本与标签）
- 识别历史：按账号隔离，可回看结果并导出
- 实时识别（摄像头 / 麦克风，人脸与语音情感）
- 导出 Excel（后端）与 CSV（前端，基于当前编辑结果）

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 语音识别 | FunASR Paraformer large（VAD + 标点） |
| 情感识别 | emotion2vec+ large |
| 音视频处理 | ffmpeg + ffmpeg-python |
| 前端框架 | Vue 3 + Vite |
| HTTP 客户端 | axios |
| 鉴权 | HttpOnly Cookie + HMAC token |

## 情感标签

### 9 类标签（emotion2vec 原始，默认）

| 值 | 英文 | 中文 |
|----|------|------|
| 0 | angry | 愤怒 |
| 1 | disgusted | 厌恶 |
| 2 | fearful | 恐惧 |
| 3 | happy | 开心 |
| 4 | neutral | 中性 |
| 5 | other | 其他 |
| 6 | sad | 悲伤 |
| 7 | surprised | 惊讶 |
| 8 | unknown | 未知 |

前端默认 `ENABLE_TEACHER_EMOTION = false`，UI 与导出使用 9 类。

### 4 类标签（教学场景，可选）

| 标签 | 中文 | 说明 |
|------|------|------|
| 0 - enthusiastic | 热情投入 | 积极、兴奋 |
| 1 - calm | 平稳中性 | 中性、平稳 |
| 2 - negative | 消极低落 | 消极、悲伤 |
| 3 - tense | 紧张焦虑 | 紧张、焦虑 |

将 `frontend/src/emotionConfig.js` 中 `ENABLE_TEACHER_EMOTION` 设为 `true` 可恢复教师 4 类 UI。

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
python main.py
# Server at http://localhost:8000
# API prefix: /api
```

首次启动会写入 `backend/storage/users.json`，默认账号：

- 用户名：`account`
- 密码：`password`

请登录后及时修改；运维也可直接编辑 `users.json`。`storage/` 已在 `.gitignore` 中，不会入库。

### Frontend

```bash
cd frontend
npm install
npm run dev
# UI at http://localhost:5173
```

### 内存与模型（通用情感，默认）

默认只跑 **emotion2vec 通用情感**，并做按需加载以压内存：

| 环境变量 | 默认 | 说明 |
|----------|------|------|
| `EMOTION_MODEL` | `emotion2vec` | `custom` 才加载教师多模态（更吃内存） |
| `EMOTION2VEC_MODEL_ID` | `iic/emotion2vec_plus_large` | 保精度；可改 `emotion2vec_base` 更省 |
| `ASR_BACKEND` | `paraformer` | 可设 `sensevoice` 更省内存 |
| `PUNC_MODEL` | `default`（中等词表） | `large` 恢复大标点；`none` 不加载标点 |
| `PRELOAD_EMOTION` | `true` | `false` 则首次任务再加载情感模型 |
| `PRELOAD_FACE` | `false` | 人脸仅实时识别时按需加载 |
| `RELEASE_MODELS_AFTER_JOB` | `false` | `true` 则任务后释放 ASR/情感模型 |

启动日志会打印当前 Memory profile。

### 本地冒烟测试

```bash
cd backend
# 需先将授课视频放到 storage/uploads/Psychology-01.mp4
python scripts/smoke_test_video.py
```

覆盖：emotion2vec 段级识别、ASR 转写、短视频切分与 mini pipeline。输出 `SMOKE_OK` 表示通过。

## 主要 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录，写 Cookie |
| POST | `/api/auth/logout` | 退出 |
| GET | `/api/auth/me` | 当前用户 |
| GET | `/api/history` | 当前账号识别历史 |
| GET | `/api/history/{job_id}/result` | 历史任务结果 |
| POST | `/api/upload` | 上传视频并启动任务 |
| GET | `/api/jobs/{job_id}/progress` | SSE 进度流 |
| GET | `/api/jobs/{job_id}/result` | 任务结果（处理中返回 partial） |
| GET | `/api/jobs/{job_id}/video/{index}` | 分段视频 |
| GET/POST | `/api/jobs/{job_id}/export` | Excel 导出 |
| WS | `/api/ws/realtime` | 实时识别 |

除登录外，业务接口均需登录 Cookie。

## 项目结构

```
ter/
├── README.md
├── backend/
│   ├── main.py                  # FastAPI 入口
│   ├── requirements.txt
│   ├── api/
│   │   ├── routes.py            # REST / SSE / WS 路由
│   │   └── schemas.py           # Pydantic 数据模型
│   ├── core/
│   │   ├── asr.py               # FunASR Paraformer ASR
│   │   ├── segmentation.py      # 视频按句子切分
│   │   ├── recognizer.py        # emotion2vec 情感识别
│   │   ├── auth.py              # 登录鉴权
│   │   ├── history.py           # 识别历史持久化
│   │   ├── memory_config.py     # 内存/模型环境配置
│   │   ├── face_recognizer.py   # 人脸表情（实时）
│   │   ├── custom_predictor.py  # 教师多模态（可选）
│   │   └── ffmpeg_utils.py      # ffmpeg 音视频工具
│   ├── tasks/
│   │   └── manager.py           # 后台任务 + SSE
│   ├── scripts/
│   │   └── smoke_test_video.py  # 本地链路冒烟
│   └── storage/                 # 上传与任务产物（git 忽略）
└── frontend/
    ├── src/
    │   ├── App.vue
    │   ├── api.js               # HTTP / SSE 客户端
    │   ├── emotionConfig.js     # 情感标签配置
    │   ├── exportUtils.js       # 前端 CSV 导出
    │   └── components/
    │       ├── LoginView.vue
    │       ├── HistoryPanel.vue
    │       ├── VideoUpload.vue
    │       ├── ProgressPanel.vue
    │       ├── VideoPlayer.vue
    │       ├── EmotionTimeline.vue
    │       ├── ResultTable.vue
    │       └── RealtimeRecognition.vue
    └── package.json
```
