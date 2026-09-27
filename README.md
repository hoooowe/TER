# TER · classroom-emotion

**教师情感识别**（分支 `classroom-emotion`）— 仅保留教学情绪-行为双维自动编码。

## 功能（本分支）

1. **双维编码（教学情绪-行为）**：面向微格/模拟教学，按论文第三章编码体系自动输出教学行为编码（B1–B15）与可观察教学情绪编码（E1–E3 / U1 / N1–N2 / X0）。ASR 使用 `qwen3-asr-flash`，多模态使用 `qwen3.8-omni-flash`。一个编码单元 = 一个行为码 + 一个情绪码；边识别边展示，支持人工复核并导出标准化双维编码表。
2. **识别历史**：查看/删除双维任务，打开复核与导出。

> 通用 emotion2vec 视频分析、实时人脸/语音识别不在本分支范围。

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
