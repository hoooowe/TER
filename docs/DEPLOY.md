# 部署说明（教室情感识别 · 双维编码）

> 仅 `classroom-emotion` 分支：教学情绪-行为双维自动编码。
> 通义 ASR + 可配置的 OpenAI 兼容多模态 API，**服务器无需 GPU / torch**。

## 1. 环境要求

| 项 | 要求 |
|----|------|
| OS | Ubuntu 22.04 / Debian 12 / macOS |
| Python | 3.10+ |
| Node | 18+（前端构建） |
| 系统包 | **ffmpeg**（抽音频、抽帧） |
| 规格 | **2 核 2G～4G** 起（仅 API 代理） |
| 网络 | 可访问 ASR 端点及所配置的多模态模型端点 |

```bash
# Debian/Ubuntu
sudo apt-get install -y ffmpeg
# macOS
brew install ffmpeg
```

## 2. 配置

将 `backend/.env.example` 复制为 `backend/.env`（不要提交密钥），填入两个服务各自的密钥。示例使用通义语音识别和 Moonshot 中国区 Kimi-K2.6：

```bash
DASHSCOPE_API_KEY=sk-xxxx
ALIYUN_ASR_MODEL=qwen3-asr-flash
ALIYUN_ASR_BASE_URL=https://maas.qianwenaiapi.com/api/v1
VL_PROVIDER=moonshot
VL_API_KEY=your-moonshot-key
VL_MODEL=kimi-k2.6
VL_BASE_URL=https://api.moonshot.cn/v1
VL_THINKING=disabled
VL_TEMPERATURE=
VL_MAX_TOKENS=40960
VL_TIMEOUT_SEC=120
VL_MODALITIES=
DUAL_FRAMES_MODE=adaptive
DUAL_FRAMES_PER_UNIT=8
```

配置在后端启动时加载，**修改后需重启后端**。同名键优先级：进程环境变量 > `backend/.env` > 仓库根目录 `.env`；支持 BOM、单/双引号、`export KEY=value` 和空白后的行尾注释。

| 变量 | 用途 |
|---|---|
| `VL_PROVIDER` | 参数默认值类型：`aliyun` 保留原行为；`moonshot` 或 `openai-compatible` 默认省略温度和 `modalities`。服务地址始终由 `VL_BASE_URL` 决定 |
| `VL_MODEL` | 服务商的模型 ID；优先于旧 `ALIYUN_VL_MODEL` |
| `VL_BASE_URL` | 包含版本路径的 API 基址（例如 `/v1`），也接受完整 `/chat/completions` URL；优先于旧 `ALIYUN_VL_BASE_URL` |
| `VL_API_KEY` | 多模态服务的密钥，与 ASR 独立；仅 `aliyun` 模式允许回落到 `DASHSCOPE_API_KEY` |
| `VL_THINKING` | `enabled` / `disabled`；留空不发送 `thinking`，交由服务商决定 |
| `VL_TEMPERATURE` | 数值或留空；留空不发送该参数，使用服务商默认值 |
| `VL_MAX_TOKENS` | 输出 token 上限；阿里云默认 800，其它提供商默认 4096 |
| `VL_TIMEOUT_SEC` | 单次 HTTP 调用超时（秒），默认沿用 `ALIYUN_TIMEOUT_SEC` 或 120 |
| `VL_MODALITIES` | 逗号分隔的 `modalities` 值；留空不发送。阿里云未配置时默认 `text` |

旧阿里云部署无需修改原变量即可运行。切回通义时可配置 `VL_PROVIDER=aliyun`、通义的 `VL_MODEL` / `VL_BASE_URL`，并清空或更新 `VL_API_KEY`、`VL_THINKING`；若需要原请求中的 `modalities`，设置 `VL_MODALITIES=text`。

### Kimi-K2.6 兼容性

- 官方模型 ID 为 `kimi-k2.6`，中国区端点为 `https://api.moonshot.cn/v1`；其它区域或第三方网关请填写对应地址、密钥和模型 ID。
- 现有 JPEG base64 `image_url` + 文本输入及 `choices[0].message.content` 响应解析可复用。请求保持非流式，任务进度仍由项目自身的 SSE 推送。
- Kimi-K2.6 思考模式温度只接受 `1.0`，非思考模式只接受 `0.6`；原固定 `0.2` 不适配。示例留空温度，由 Kimi 使用默认值，并通过 `thinking={"type":"disabled"}` 使用非思考模式。
- Kimi 请求默认不携带原 Omni 调用中的 `modalities` 字段；需要其它扩展字段的服务应另行适配。
- 原 800 token 上限不适合直接沿用于思考模式。示例配置 40960 token 作为输出上限，可按实际任务调整；启用思考时应保留充足预算，温度留空或改为 `1.0`。客户端将 `finish_reason=length` 和空最终文本视为调用失败，标记零置信度、待复核，避免误认为识别成功。
- 当前输入仍为视频抽帧和转写文本，不包含原始音频；模型更换不会自动增加语调证据。

官方依据：[Kimi-K2.6 快速开始](https://platform.moonshot.cn/docs/guide/kimi-k2-6-quickstart)、[Moonshot 官方模型说明](https://huggingface.co/moonshotai/Kimi-K2.6)。第三方服务的扩展字段可能与官方不同，接入时应核对其文档。

## 3. 启动

```bash
# 后端
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py          # http://0.0.0.0:8000

# 前端（开发）
cd frontend
npm install
npm run dev             # http://localhost:5173

# 前端（生产构建后交给 Nginx）
npm run build           # 产物 frontend/dist
```

## 4. Nginx 示例

```nginx
server {
    listen 80;
    server_name your.domain;

    location / {
        root /srv/emotion/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 600s;
    }
}
```

后端 systemd 示例：

```ini
[Service]
WorkingDirectory=/srv/emotion/backend
ExecStart=/srv/emotion/backend/.venv/bin/python main.py
Restart=always
```

## 5. 存储

| 路径 | 内容 |
|------|------|
| `backend/storage/uploads/` | 原始视频 |
| `backend/storage/jobs/<id>/` | meta / dual_result / 矩阵 |
| `backend/storage/users.json` | 账号 |

历史页可删除任务；可定期清理 `uploads` 与 `jobs`。

## 6. 与旧版差异

- **不再**依赖：torch、funasr、emotion2vec、mediapipe、人脸/实时识别
- **依赖**：FastAPI、dashscope、openpyxl、pydantic + 系统 ffmpeg
- 建议 `uvicorn` 单 worker 即可；并发靠 API 限流与任务队列串行

## 7. 配置与协议离线测试

```bash
cd backend
python -m unittest discover -s tests -v
```

测试使用独立环境和模拟 HTTP，验证配置优先级、旧配置兼容、图片请求和失败复核，不会调用或计费远程模型。
