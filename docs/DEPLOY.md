# 部署说明（教室情感识别 · 双维编码）

> 仅 `classroom-emotion` 分支：教学情绪-行为双维自动编码。
> 模型全部走通义 API，**服务器无需 GPU / torch**。

## 1. 环境要求

| 项 | 要求 |
|----|------|
| OS | Ubuntu 22.04 / Debian 12 / macOS |
| Python | 3.10+ |
| Node | 18+（前端构建） |
| 系统包 | **ffmpeg**（抽音频、抽帧） |
| 规格 | **2 核 2G～4G** 起（仅 API 代理） |
| 网络 | 可访问 `maas.qianwenaiapi.com` |

```bash
# Debian/Ubuntu
sudo apt-get install -y ffmpeg
# macOS
brew install ffmpeg
```

## 2. 配置

`backend/.env`（不要提交仓库）：

```bash
DASHSCOPE_API_KEY=sk-xxxx
ALIYUN_ASR_MODEL=qwen3-asr-flash
ALIYUN_ASR_BASE_URL=https://maas.qianwenaiapi.com/api/v1
ALIYUN_VL_MODEL=qwen3.8-omni-flash
ALIYUN_VL_BASE_URL=https://maas.qianwenaiapi.com/compatible-mode/v1
DUAL_FRAMES_MODE=adaptive
DUAL_FRAMES_PER_UNIT=8
```

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
