#!/usr/bin/env python3
"""
Phase 2 Step 2.2: Per-Video Analysis

Analyzes each video individually using LLM.
Produces report_per_video.json with one item per video.
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
import re

# Add script directory to path for imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from llm_factory import get_default_client
from llm_client import LLMClient, LLMError, LLMRateLimitError, LLMConfigError
from utils import calculate_days_ago, summarize_video_time_window
from feishu_notify import push_error_notification


# Configuration
BASE_DIR = SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "trend-scrap" / "tiktok-scraper" / "data"
RESULT_FILE = DATA_DIR / "filtered-result.json"
PROMPT_FILE = BASE_DIR / "references" / "prompt_for_each_video.txt"


def format_number(num):
    """Format number to K/M format"""
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    else:
        return str(num)


def format_video_for_prompt(video, index):
    """Format a single video for the prompt"""
    video_id = video.get('id', 'unknown')
    text = video.get('text', video.get('desc', ''))
    author = video.get('authorMeta', {}).get('nickName', 'unknown')
    likes = video.get('diggCount', 0)
    views = video.get('playCount', 0)
    create_time = video.get('createTime', video.get('createTimeISO', ''))
    summary = video.get('video_summary', 'No summary available')

    days_ago = calculate_days_ago(video)
    
    tiktok_url = f"https://www.tiktok.com/@user/video/{video_id}"
    
    return f"""### 视频 {index}
- ID: {video_id}
- 标题/描述: {text[:200]}
- 作者: {author}
- 点赞: {format_number(likes)}
- 播放: {format_number(views)}
- 发布时间: {create_time} ({days_ago}天前)
- 链接: {tiktok_url}
- AI分析摘要:
{summary}
"""


def parse_json_from_response(response_text):
    """Extract JSON from the API response"""
    json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            raise Exception("Could not find JSON in response")
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        debug_file = Path(__file__).parent / "debug_parse_failure.txt"
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(f"JSONDecodeError: {e}\n")
            f.write(f"Extracted JSON string (first 2000 chars):\n")
            f.write(json_str[:2000])
        raise


def normalize_product_benchmark(points):
    """Normalize product benchmark: accept valid suggestions, discard empty/placeholder ones."""
    if not isinstance(points, list):
        points = []

    normalized = []
    for p in points:
        s = str(p).strip()
        if not s:
            continue
        # Discard obvious placeholder/abandoned content
        if any(placeholder in s for placeholder in ["具体结果", "具体图片类型", "具体什么样的"]):
            continue
        normalized.append(s)

    # If nothing valid was produced, generate a proper fallback based on category
    if not normalized:
        normalized = [
            "建议结合视频具体玩法，选择 Guru 图像或视频类产品（如 ImagineFlow / Toki）中最匹配的已有功能，设计对应的素材生成入口。",
            "优先选择用户已有照片作为输入，降低创作门槛，提升社交传播属性。",
            "生成的素材需在 3 秒内制造视觉钩子，适配 TikTok 短视频节奏。"
        ]
    return normalized[:3]


def analyze_single_video(llm_client: LLMClient, prompt_template: str, video: dict, category: str) -> dict:
    """Analyze a single video using LLM."""
    video_text = format_video_for_prompt(video, 1)
    
    # Build core data summary
    likes = video.get('diggCount', 0)
    views = video.get('playCount', 0)
    days_ago = calculate_days_ago(video)
    core_data = f"{format_number(views)}播放，{format_number(likes)}点赞，发布{days_ago}天"

    analysis_prompt = f"""分析以下这条TikTok视频：

分类标签：{category}

{video_text}

核心数据：{core_data}

请输出严格JSON，字段如下（不要其他字段）：
{{
  "trend_title": "",
  "core_data": "{core_data}",
  "background": "2-4句，说明谁在做什么+用了什么AI+爆点+为什么火",
  "ua_suggestion": "1-3句UA建议：用户输入什么、生成什么、广告怎么拍",
  "product_benchmark": ["Guru 可以出一个【图片特效/视频特效】玩法，用户上传【具体图片类型】，生成【具体结果】。这个玩法的吸引力在于【用户吸引点/传播点】"],
  "risk_notes": [""],
  "trend_stage": {{
    "label": "24H突发·爆发期 / 3日持续上升 / 持续长红 / 已过峰值 / 24H突发·节日驱动",
    "reason": ""
  }}
}}

【重要】JSON字符串值中不要使用ASCII双引号""包裹内容；如需引用，请使用中文引号「」或尖括号〔〕替代。
"""
    
    response = llm_client.call(prompt_template, analysis_prompt)
    data = parse_json_from_response(response)

    return {
        "category_tag": category,
        "trend_title": data.get("trend_title", "未知趋势"),
        "core_data": data.get("core_data", core_data),
        "background": data.get("background", "暂无"),
        "ua_suggestion": data.get("ua_suggestion", "暂无"),
        "product_benchmark": normalize_product_benchmark(data.get("product_benchmark", []) or []),
        "risk_notes": data.get("risk_notes", []) or [],
        "trend_stage": data.get("trend_stage", {"label": "待判断", "reason": "暂无"}),
        # Include video metadata for reference
        "video_id": str(video.get('id')),
        "video_url": video.get('videoMeta', {}).get('webVideoUrl') or f"https://www.tiktok.com/@user/video/{video.get('id')}",
        "video_title": video.get('text', '')[:80],
        "author": video.get('authorMeta', {}).get('nickName', 'unknown'),
        "likes": video.get('diggCount', 0),
        "views": video.get('playCount', 0),
        "days_ago": days_ago
    }


def build_report(videos: list, items: list) -> dict:
    """Build the final per-video report structure."""
    period_hours, time_range = summarize_video_time_window(videos)

    report = {
        "title": "TikTok AI玩法日报 - 单视频分析",
        "platform": "TikTok",
        "topic": "AI玩法",
        "period_hours": period_hours,
        "time_range": time_range,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "valid_hot_count": len(videos),
        "analysis_type": "per_video",
        "items": items
    }
    
    return report


def analyze_all_videos(videos: list, category_map: dict, prompt_template: str) -> list:
    """Analyze all videos individually."""
    # Build reverse mapping: video_id -> category
    video_to_category = {}
    for cat, ids in category_map.items():
        for vid in ids:
            video_to_category[vid] = cat
    
    items = []
    
    try:
        llm_client = get_default_client()
        print(f"Using LLM: {llm_client.get_model_name()}")
    except LLMConfigError as e:
        raise ValueError(f"Failed to initialize LLM client: {e}")

    total = len(videos)
    for i, video in enumerate(videos, 1):
        vid = str(video.get('id'))
        category = video_to_category.get(vid, "ai视频玩法")  # Default fallback
        
        print(f"\n[{i}/{total}] Analyzing video {vid[:20]}... ({category})")
        
        try:
            item = analyze_single_video(llm_client, prompt_template, video, category)
            items.append(item)
            print(f"  ✅ {item['trend_title'][:50]}...")
        except Exception as e:
            print(f"  ⚠️ Failed: {e}")
            # Add fallback item
            items.append({
                "category_tag": category,
                "trend_title": f"{category} - 分析失败",
                "core_data": "分析失败",
                "background": f"分析失败: {e}",
                "ua_suggestion": "请重试",
                "product_benchmark": [],
                "risk_notes": ["分析失败"],
                "trend_stage": {"label": "待判断", "reason": "分析失败"},
                "video_id": vid,
                "video_url": video.get('videoMeta', {}).get('webVideoUrl') or f"https://www.tiktok.com/@user/video/{vid}",
                "video_title": video.get('text', '')[:80],
                "author": video.get('authorMeta', {}).get('nickName', 'unknown'),
                "likes": video.get('diggCount', 0),
                "views": video.get('playCount', 0),
                "days_ago": calculate_days_ago(video)
            })
    
    return items


def analyze_with_retry(videos: list, category_map: dict, prompt_template: str, max_retries: int = 3) -> list:
    """Analyze with retry logic at the batch level."""
    for attempt in range(1, max_retries + 1):
        print(f"\n{'='*50}")
        print(f"Per-Video Analysis attempt {attempt}/{max_retries}")
        print(f"{'='*50}")
        
        try:
            items = analyze_all_videos(videos, category_map, prompt_template)
            print(f"\n✅ Analysis complete: {len(items)} videos analyzed")
            return items
            
        except LLMRateLimitError as e:
            print(f"⚠️ Rate limit: {e}")
            if attempt < max_retries:
                import time
                time.sleep(5 * attempt)
            else:
                notified = push_error_notification(f"Phase 2.2.2 Per-Video Analysis failed (attempt {attempt}/{max_retries})\n{e}")
                if not notified:
                    print("⚠️ Warning: Failed to send Feishu error notification")
                raise
                
        except (LLMError, Exception) as e:
            print(f"⚠️ Error: {e}")
            import traceback
            traceback.print_exc()
            if attempt < max_retries:
                import time
                time.sleep(2)
            else:
                notified = push_error_notification(f"Phase 2.2.2 Per-Video Analysis failed after {max_retries} retries\n{e}")
                if not notified:
                    print("⚠️ Warning: Failed to send Feishu error notification")
                raise
    
    raise Exception(f"Analysis failed after {max_retries} attempts")


def main():
    parser = argparse.ArgumentParser(description='Phase 2 Step 2.2: Per-Video Analysis')
    parser.add_argument('--category-map', '-c', type=str, required=True,
                        help='Input category_map.json from classification step')
    parser.add_argument('--output', '-o', type=str, required=True,
                        help='Output file for report_per_video.json')
    parser.add_argument('--max-retries', '-r', type=int, default=3,
                        help='Maximum retry attempts (default: 3)')
    args = parser.parse_args()
    
    # Load videos
    if not RESULT_FILE.exists():
        print(f"ERROR: Result file not found: {RESULT_FILE}")
        sys.exit(1)
    
    with open(RESULT_FILE, 'r', encoding='utf-8') as f:
        videos = json.load(f)
    
    print(f"Loaded {len(videos)} videos")
    
    # Load category map
    category_map_file = Path(args.category_map)
    if not category_map_file.exists():
        print(f"ERROR: Category map not found: {category_map_file}")
        print("Run phase2_classify.py first!")
        sys.exit(1)
    
    with open(category_map_file, 'r', encoding='utf-8') as f:
        category_map = json.load(f)
    
    print(f"Loaded category map: { {k: len(v) for k, v in category_map.items()} }")
    
    # Load prompt template
    if not PROMPT_FILE.exists():
        print(f"ERROR: Prompt file not found: {PROMPT_FILE}")
        sys.exit(1)
    
    with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
        prompt_template = f.read()
    
    # Analyze
    try:
        items = analyze_with_retry(videos, category_map, prompt_template, args.max_retries)
    except Exception as e:
        print(f"ERROR: Analysis failed: {e}")
        sys.exit(1)
    
    # Build report
    report = build_report(videos, items)
    
    # Save output
    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Per-video report saved to: {output_file}")
    print(f"   Total videos: {report['valid_hot_count']}")
    print(f"   Analyzed items: {len(report['items'])}")
    sys.exit(0)


if __name__ == "__main__":
    main()
