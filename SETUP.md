# TikTok Feishu Radar - 环境与使用说明

## 项目简介

这个项目会自动完成以下流程：

1. 从飞书读取产品手册并更新提示词
2. 抓取 TikTok 上与 AI 相关的热视频
3. 调用视频摘要服务生成 `video_summary`
4. 用 LLM 做分类、趋势分析和单视频分析
5. 生成飞书卡片并推送，同时可写入飞书多维表

当前推荐入口是：

```bash
python run_pipeline.py
```

## 环境要求

- Python 3.11+
- Node.js 18+
- npm

现在 Phase 1 已经不再依赖 `bash` 和 `jq`。

## Python 虚拟环境

### Windows

```powershell
python -m venv .venv-win
.\.venv-win\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Node 依赖

TikTok 抓取器依赖 Node 包：

```bash
cd trend-scrap/tiktok-scraper
npm install
```

如果仓库里已经有 `node_modules`，一般可以跳过。

## 配置文件

项目主要使用两份 `.env`。

### 1. `scripts/.env`

用于 LLM、飞书卡片推送和 bitable：

```env
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/your-webhook

FEISHU_APP_ID=your_feishu_app_id
FEISHU_APP_SECRET=your_feishu_app_secret
FEISHU_CHAT_ID=your_feishu_chat_id
BITABLE_APP_TOKEN=your_bitable_app_token

OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_MODEL=anthropic/claude-opus-4.6

ANTHROPIC_API_KEY=your_minimax_or_anthropic_compatible_key
```

说明：

- `FEISHU_WEBHOOK` 存在时，飞书推送优先走 webhook
- `FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_CHAT_ID` 仍用于应用消息兜底和 bitable 写入
- 默认 provider 仍是 `openrouter`
- 现在支持通过环境变量覆盖 provider：

```bash
LLM_PROVIDER=minimax python run_pipeline.py
```

### 2. `trend-scrap/tiktok-scraper/.env`

用于抓取和视频摘要：

```env
APIFY_TOKEN=your_apify_token
MEMORIES_API_KEY=your_memories_key
```

## 推荐运行方式

### 跑完整流程

```bash
python run_pipeline.py
```

### 只跑到 Phase 2，不推送飞书

```bash
python run_pipeline.py --skip-phase3
```

### 从 Phase 2 开始

```bash
python run_pipeline.py --phase2
```

### 只跑分类后的分类趋势分析

```bash
python run_pipeline.py --phase2-analysis
```

### 只跑单视频分析

```bash
python run_pipeline.py --phase2-per-video
```

### 只推送已有报告

```bash
python run_pipeline.py --phase3
```

### 跳过单视频分析

```bash
python run_pipeline.py --no-per-video
```

## 分阶段运行

### Stage 1：更新产品手册提示词

```bash
python scripts/update_prompt_with_product_manual.py
```

### Phase 1：抓取并生成视频摘要

```bash
python scripts/phase1_scrape.py
```

### Phase 2.1：分类

```bash
python scripts/phase2_classify.py --output skill_runs/category_map.json --max-retries 3
```

### Phase 2.2.1：分类趋势分析

```bash
python scripts/phase2_analyze.py --category-map skill_runs/category_map.json --output skill_runs/report.json --max-retries 3
```

### Phase 2.2.2：单视频分析

```bash
python scripts/phase2_analyze_per_video.py --category-map skill_runs/category_map.json --output skill_runs/report_per_video.json --max-retries 3
```

### Phase 3：生成并推送飞书卡片

```bash
python scripts/phase3_push.py --report skill_runs/report.json --raw trend-scrap/tiktok-scraper/data/filtered-result.json --report-per-video skill_runs/report_per_video.json --card-output skill_runs/latest_feishu_card.json
```

## 定时任务

项目新增了一个每日调度脚本：

```bash
python run_daily_schedule.py
```

调度逻辑：

- 每天 `08:00` 开始执行 Stage 1 + Phase 1 + Phase 2
- 每天 `09:00` 执行 Phase 3 飞书推送
- 如果分析超过 09:00，则分析完成后立即推送
- 默认以 `UTC+8` 作为北京时间执行
- 调度脚本默认会设置 `LLM_PROVIDER=minimax`

### Windows 后台启动示例

```powershell
Start-Process -FilePath .\.venv-win\Scripts\python.exe -ArgumentList "run_daily_schedule.py"
```

当前仓库里已经落盘的调度辅助文件：

- `skill_runs/daily_scheduler.pid`
- `skill_runs/daily_scheduler.stdout.log`
- `skill_runs/daily_scheduler.stderr.log`

## 输出文件

- `trend-scrap/tiktok-scraper/data/filtered-result.json`
  - 抓取并补充摘要后的 TikTok 视频结果
- `skill_runs/category_map.json`
  - 分类结果
- `skill_runs/report.json`
  - 分类级趋势报告
- `skill_runs/report_per_video.json`
  - 单视频分析报告
- `skill_runs/<timestamp>/feishu_card.json`
  - 本次推送使用的飞书卡片 JSON

## 常见问题

### 1. Windows 下跑不起来

优先使用：

```powershell
.\.venv-win\Scripts\python.exe run_pipeline.py
```

### 2. OpenRouter 模型报区域限制

可以改用 MiniMax：

```powershell
$env:LLM_PROVIDER='minimax'
.\.venv-win\Scripts\python.exe run_pipeline.py
```

### 3. 依赖装完后仍提示 `No module named openai`

重新安装依赖：

```bash
python -m pip install -r requirements.txt
```

### 4. 飞书推送失败

优先检查：

- `FEISHU_WEBHOOK`
- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_CHAT_ID`
- `BITABLE_APP_TOKEN`

### 5. 定时任务需要停止

Windows 下可以执行：

```powershell
Stop-Process -Id (Get-Content skill_runs\daily_scheduler.pid)
```
