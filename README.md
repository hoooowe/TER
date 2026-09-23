# TER

**Teacher Emotion Recognition** — 教师情感识别系统。

## 功能

1. **视频分析（通用情感）**：上传教学视频后，按句子切分音频，用 FunASR Paraformer 做中文语音识别，用 emotion2vec+ 识别每句话的情感，支持登录、历史任务、在线编辑与导出。
2. **双维编码（教学情绪-行为）**：面向微格/模拟教学，按论文第三章编码体系自动输出教学行为编码（B1–B15）与可观察教学情绪编码（E1–E3 / U1 / N1–N2 / X0）。ASR 使用 `qwen3-asr-flash`，多模态使用 `qwen3.8-omni-flash`。一个编码单元 = 一个行为码 + 一个情绪码；支持人工复核并导出标准化双维编码表（含编码手册、过程指标、行为连接/情绪转换/共现矩阵）。
3. **实时识别**：摄像头 + 麦克风流式人脸/语音情感。

## 技术栈

- 后端：FastAPI + Vue 3
- 通用情感：FunASR / emotion2vec+
- 双维编码：阿里云 DashScope（`DASHSCOPE_API_KEY`）

## 双维编码配置（`backend/.env` 或环境变量）

| 变量 | 说明 | 默认 |
|------|------|------|
| `DASHSCOPE_API_KEY` | 通义/DashScope API Key（必填） | 读取 `backend/.env` |
| `ALIYUN_ASR_MODEL` | 语音识别模型 | `qwen3-asr-flash` |
| `ALIYUN_ASR_BASE_URL` | ASR 端点 | `https://maas.qianwenaiapi.com/api/v1` |
| `ALIYUN_VL_MODEL` | 多模态大模型 | `qwen3.8-omni-flash` |
| `ALIYUN_VL_BASE_URL` | OpenAI 兼容端点 | `https://maas.qianwenaiapi.com/compatible-mode/v1` |
| `DUAL_CONFIDENCE_THRESHOLD` | 低置信度复核阈值 | `0.70` |
| `DUAL_FRAMES_MODE` | 抽帧策略 | `adaptive`（4/8/12） |
| `DUAL_FRAMES_PER_UNIT` | 目标帧数（高精度 8 帧） | `8` |

## 启动

```bash
# 后端（API Key 写在 backend/.env，勿提交仓库）
cd backend
pip install -r requirements.txt
python main.py

# 前端
cd frontend
npm install
npm run dev
```
