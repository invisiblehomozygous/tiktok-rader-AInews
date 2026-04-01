---
name: tiktok-feishu-radar
description: TikTok AI trend pipeline that scrapes, summarizes, analyzes, and pushes a Feishu report on demand or on a daily schedule.
---

# TikTok Feishu Radar

## 项目定位

这是一个从 TikTok 热点抓取到飞书日报推送的自动化流水线，适合每天定时产出 AI 相关热视频趋势报告。

当前主入口已经从 `run_pipeline.sh` 切换为：

```bash
python run_pipeline.py
```

## 当前流水线

### 完整流程

1. Stage 1：从飞书读取产品手册并更新提示词
2. Phase 1：抓取 TikTok 视频、筛选 AI 相关内容、生成 `video_summary`
3. Phase 2.1：对视频进行三分类
4. Phase 2.2.1：做分类级趋势分析
5. Phase 2.2.2：做单视频分析
6. Phase 3：生成飞书卡片并推送，同时写入 bitable

### 默认输出

- `skill_runs/category_map.json`
- `skill_runs/report.json`
- `skill_runs/report_per_video.json`
- `skill_runs/<timestamp>/feishu_card.json`

## 关键命令

### 跑完整流程

```bash
python run_pipeline.py
```

### 只跑到分析，不推送飞书

```bash
python run_pipeline.py --skip-phase3
```

### 只推送已有报告

```bash
python run_pipeline.py --phase3
```

### 使用 MiniMax 作为临时 provider

```bash
LLM_PROVIDER=minimax python run_pipeline.py
```

Windows PowerShell：

```powershell
$env:LLM_PROVIDER='minimax'
.\.venv-win\Scripts\python.exe run_pipeline.py
```

## 飞书推送规则

- 如果 `scripts/.env` 里存在 `FEISHU_WEBHOOK`，推送优先走机器人 webhook
- 如果没有 `FEISHU_WEBHOOK`，则退回到飞书应用消息方式
- bitable 写入仍依赖应用凭证

## 定时任务

项目内置每日调度脚本：

```bash
python run_daily_schedule.py
```

调度行为：

- 每天 `08:00` 开始抓取和分析
- 每天 `09:00` 推送飞书
- 如果分析尚未完成，则分析完成后立即推送
- 默认使用 `UTC+8`
- 默认自动设置 `LLM_PROVIDER=minimax`

调度运行时会在 `skill_runs` 下写入：

- `daily_scheduler.pid`
- `daily_scheduler.stdout.log`
- `daily_scheduler.stderr.log`

## 使用建议

- 日常手动执行优先用 `run_pipeline.py`
- 自动化发送优先用 `run_daily_schedule.py`
- 如果 OpenRouter 模型受区域限制，优先切到 `LLM_PROVIDER=minimax`
- 如果只是调试分析，不要直接跑完整流程，优先使用 `--skip-phase3`
