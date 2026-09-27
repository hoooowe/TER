# TER · classroom-emotion

**教师情感识别** — 教学情绪-行为双维自动编码（分支 `classroom-emotion`）。

上传微格/模拟教学视频，按论文编码体系自动输出：

- **教学行为** B1–B15（知识讲授 / 教学互动 / 教学操作 / 课堂组织 / 授课失误）
- **可观察教学情绪** E1–E3 / U1 / N1–N2 / **X0**
- 同一时间轴：一个编码单元 = 一个行为码 + 一个情绪码
- 边识别边展示，人工复核后导出标准化双维编码表（含编码手册、过程指标、三种矩阵）

## 技术栈

| 部分 | 方案 |
|------|------|
| 前端 | Vue 3 + Vite |
| 后端 | FastAPI |
| ASR | 阿里云 `qwen3-asr-flash` |
| 多模态 | `qwen3.8-omni-flash`（OpenAI 兼容） |
| 导出 | openpyxl（Excel） |

## 配置（`backend/.env`）

| 变量 | 说明 | 默认 |
|------|------|------|
| `DASHSCOPE_API_KEY` | 通义 API Key（必填） | — |
| `ALIYUN_ASR_MODEL` | 语音识别 | `qwen3-asr-flash` |
| `ALIYUN_ASR_BASE_URL` | ASR 端点 | `https://maas.qianwenaiapi.com/api/v1` |
| `ALIYUN_VL_MODEL` | 多模态模型 | `qwen3.8-omni-flash` |
| `ALIYUN_VL_BASE_URL` | VL 端点 | `https://maas.qianwenaiapi.com/compatible-mode/v1` |
| `DUAL_FRAMES_MODE` | 抽帧 | `adaptive`（4/8/12 帧） |
| `DUAL_CONFIDENCE_THRESHOLD` | 待复核阈值 | `0.70` |

## 启动

```bash
# 系统依赖：ffmpeg
# 后端（Key 写入 backend/.env，勿提交仓库）
cd backend
pip install -r requirements.txt
python main.py

# 前端
cd frontend
npm install
npm run dev
```

## API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录 |
| GET | `/api/history` | 双维历史列表 |
| DELETE | `/api/history/{id}` | 删除历史 |
| POST | `/api/dual/upload` | 上传视频并开始双维编码 |
| GET | `/api/dual/jobs/{id}/progress` | SSE 实时进度 |
| GET | `/api/dual/jobs/{id}/result` | 编码结果 |
| POST | `/api/dual/jobs/{id}/export` | 导出 Excel（含编辑） |
