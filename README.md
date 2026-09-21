# TER

**Teacher Emotion Recognition** — 教师情感识别系统。

上传教学视频后，系统自动按句子切分音频，用 FunASR Paraformer 做中文语音识别，用 emotion2vec+ 识别每句话的情感，并在时间轴与结果表格中展示。支持登录后查看历史任务、在线编辑识别结果，以及导出报告。

技术栈：FastAPI + Vue 3，语音识别与情感识别基于 FunASR / emotion2vec+。
