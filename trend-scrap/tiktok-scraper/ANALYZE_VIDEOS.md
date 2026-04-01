# TikTok Video Analyzer

使用 Memories.ai API 分析 TikTok 视频内容。

## 安装依赖

```bash
pip3 install --user --break-system-packages openai requests
```

## 配置

1. 复制 `.env.example` 为 `.env`:
```bash
cp .env.example .env
```

2. 在 `.env` 中设置你的 Memories.ai API Key:
```
MEMORIES_API_KEY=sk-mai-your-key-here
```

## 使用方法

```bash
# 设置 API Key (或者在 .env 文件中设置)
export MEMORIES_API_KEY="sk-mai-your-key-here"

# 运行分析脚本
python3 analyze_videos.py
```

## 工作流程

1. 脚本读取 `data/filtered_result.json`
2. 对每个没有 `video_summary` 的视频:
   - 下载视频到 `downloaded_videos/` 目录
   - 调用 Memories.ai API 分析视频
   - 将结果保存为 `video_summary` 字段
3. 自动保存进度（每分析完一个视频）

## 输出

分析结果会更新到 `data/filtered_result.json`，每个视频条目会增加:
```json
{
  "id": "7612668737623264542",
  "video_summary": "这是视频的分析总结...",
  ...
}
```
