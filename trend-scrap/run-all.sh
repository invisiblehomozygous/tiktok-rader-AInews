#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TIKTOK_DIR="$SCRIPT_DIR/tiktok-scraper"
TIKTOK_DATA_DIR="$TIKTOK_DIR/data"
PYTHON_BIN="python3"

if [ -x "$TIKTOK_DIR/.venv/bin/python3" ]; then
    PYTHON_BIN="$TIKTOK_DIR/.venv/bin/python3"
fi

echo "🚀 开始爬取热点数据..."

# 运行 X Scraper
# echo "🐦 正在爬取 X (Twitter)..."
# cd "$SCRIPT_DIR/x-scraper" && node src/scraper.js
# X_EXIT=$?
echo "⏸️ 已暂时禁用 X (Twitter) 抓取"
X_EXIT=0

# 运行 TikTok Scraper
echo "🎵 正在爬取 TikTok..."
cd "$TIKTOK_DIR" && node src/scraper.js
TT_EXIT=$?

# TikTok: 爬取完成后，先过滤掉不含"ai"关键词的视频
# 检查字段：text, authorMeta.name, hashtags
FILTERED_RESULT="$TIKTOK_DATA_DIR/filtered-result.json"

if [ -f "$FILTERED_RESULT" ]; then
    # 先过滤：只保留包含"ai"关键词的视频（不区分大小写）
    # 检查 text, authorMeta.name, hashtags 字段
    jq '[.[] | select(
        (.text | strings | test("ai"; "i")) or
        (.authorMeta.name | strings | test("ai"; "i")) or
        (.hashtags[] | strings | test("ai"; "i")) or
        (.desc | strings | test("ai"; "i"))
    )]' "$FILTERED_RESULT" > "$FILTERED_RESULT.ai_filtered.json"
    
    AI_COUNT=$(jq 'length' "$FILTERED_RESULT.ai_filtered.json")
    ORIGINAL_COUNT=$(jq 'length' "$FILTERED_RESULT")
    
    echo "🔍 AI关键词过滤: $ORIGINAL_COUNT 条 → $AI_COUNT 条（移除不含'ai'的视频）"
    
    mv "$FILTERED_RESULT.ai_filtered.json" "$FILTERED_RESULT"
    
    # 如果过滤后没有视频，则退出
    if [ "$AI_COUNT" -eq 0 ]; then
        echo "❌ 没有找到包含AI关键词的视频，任务终止"
        exit 0
    fi
    
    # 过滤后，如果视频 >10 条，只保留播放量最高的 10 条
    VIDEO_COUNT=$(jq 'length' "$FILTERED_RESULT")
    if [ "$VIDEO_COUNT" -gt 10 ]; then
        echo "📊 检测到 $VIDEO_COUNT 条视频，保留播放量最高的 10 条..."
    fi
    # 排序并限制为10条，同时清除旧的video_summary（确保只保留本次爬取的数据）
    jq 'sort_by(.playCount) | reverse | .[:10] | map(del(.video_summary))' "$FILTERED_RESULT" > "$FILTERED_RESULT.tmp" && mv "$FILTERED_RESULT.tmp" "$FILTERED_RESULT"
fi

# 若 TikTok 爬取失败，立即退出（不要继续调用 Memories API）
if [ $TT_EXIT -ne 0 ]; then
    echo "ERROR: TikTok scraper failed (exit: $TT_EXIT), skip video analysis"
    exit $TT_EXIT
fi

# 运行 analyze_videos.py
echo "📹 正在分析 TikTok 视频..."
cd "$TIKTOK_DIR" && "$PYTHON_BIN" analyze_videos.py
ANALYZE_EXIT=$?

# 检查结果
if [ $X_EXIT -eq 0 ] && [ $TT_EXIT -eq 0 ]; then
    echo "✅ scraping complete"
else
    echo "⚠️ 爬取完成，但有部分程序返回非零退出码 (X: $X_EXIT, TikTok: $TT_EXIT)"
fi

if [ $ANALYZE_EXIT -eq 0 ]; then
    echo "✅ video analysis complete"
else
    echo "ERROR: 视频分析返回非零退出码 (analyze: $ANALYZE_EXIT)"
    exit $ANALYZE_EXIT
fi

exit 0
