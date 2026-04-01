#!/usr/bin/env python3
"""
Phase 2 Step 2: Analyze Categories

Analyzes each category using LLM and generates the final report.
Requires category_map.json from classification step.
"""

import argparse
import json
import sys
import re
from pathlib import Path
from datetime import datetime

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
PROMPT_FILE = BASE_DIR / "references" / "prompt_for_minimax.txt"


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
    author = video.get('authorMeta', {}).get('name', 'unknown')
    likes = video.get('likeCount', 0)
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
        # Debug: write failed JSON to file
        debug_file = Path(__file__).parent / "debug_parse_failure.txt"
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(f"JSONDecodeError: {e}\n")
            f.write(f"Extracted JSON string (first 2000 chars):\n")
            f.write(json_str[:2000])
        raise


def normalize_product_benchmark(category, ua_suggestion, points):
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

    # If nothing valid was produced, generate proper fallbacks
    if not normalized:
        if category == "ai视频玩法":
            normalized = [
                "建议结合视频中的 AI 剧情或动画玩法，利用 Toki 的照片转视频功能，让用户上传角色图生成对应剧情短视频。",
                "利用 Gemini 3 Pro 的视频生成能力，设计剧情化、角色驱动的玩法入口。",
                "素材需突出角色动态效果和剧情反转，快速抓住用户注意力。"
            ]
        elif category == "ai图像玩法":
            normalized = [
                "结合视频中的图像生成玩法，利用 ImagineFlow 的文生图能力设计相关素材入口，让用户输入描述词生成风格化图像。",
                "参考竞品 Midjourney / DALL·E 的热门玩法，选择用户认知度高的风格方向落地。",
                "突出 AI 生成的视觉震撼感和低门槛创作体验。"
            ]
        else:
            normalized = [
                "结合视频中的工具/滤镜玩法，选择 Guru 现有工具类产品（如 FaceAura / Evoke）中功能相近的模块进行素材设计。",
                "以用户已有照片为输入，降低参与门槛，提升传播属性。",
                "素材展示前后对比效果，直观体现工具价值。"
            ]
    return normalized[:3]


def analyze_category(llm_client: LLMClient, prompt_template: str, category: str, videos: list) -> dict:
    """Analyze one category using LLM."""
    videos_text = ""
    for i, video in enumerate(videos, 1):
        videos_text += format_video_for_prompt(video, i)

    analysis_prompt = f"""你是UA分析师。仅分析分类：{category}

输入视频：
{videos_text}

请输出严格JSON，字段如下（不要其他字段）：
{{
  "trend_title": "",
  "core_data": "",
  "background": "2-4句，说明谁在做什么+用了什么AI+爆点+为什么火",
  "ua_suggestion": "",
  "product_benchmark": ["Guru 可以出一个【图片特效/视频特效】玩法，用户上传【具体图片类型】，生成【具体结果】。这个玩法的吸引力在于【用户吸引点/传播点】"],
  "risk_notes": [""],
  "trend_stage": {{
    "label": "24H突发·爆发期 / 3日持续上升 / 持续长红 / 已过峰值 / 24H突发·节日驱动",
    "reason": ""
  }}
}}

【重要】JSON字符串值中不要使用ASCII双引号""包裹内容；如需引用，请使用中文引号「」或尖括号〔〕替代。
"""
    
    print(f"  Calling {llm_client.get_model_name()} for {category} analysis...")
    response = llm_client.call(prompt_template, analysis_prompt)
    data = parse_json_from_response(response)

    ua_suggestion = data.get("ua_suggestion", "暂无")
    return {
        "category_tag": category,
        "trend_title": data.get("trend_title", f"{category} 趋势"),
        "core_data": data.get("core_data", "暂无"),
        "background": data.get("background", "暂无"),
        "ua_suggestion": ua_suggestion,
        "product_benchmark": normalize_product_benchmark(category, ua_suggestion, data.get("product_benchmark", []) or []),
        "risk_notes": data.get("risk_notes", []) or [],
        "trend_stage": data.get("trend_stage", {"label": "待判断", "reason": "暂无"}),
        "reference_links": [],
        "representative_videos": []
    }


def build_report(videos: list, category_map: dict, items: list) -> dict:
    """Build the final report structure."""
    period_hours, time_range = summarize_video_time_window(videos)

    report = {
        "title": "TikTok AI玩法日报",
        "platform": "TikTok",
        "topic": "AI玩法",
        "period_hours": period_hours,
        "time_range": time_range,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "valid_hot_count": len(videos),
        "trend_overview": "基于分类后的视频样本自动生成三类趋势分析。",
        "items": items,
        "category_map": category_map
    }
    
    return report


def analyze_all_categories(videos: list, category_map: dict, prompt_template: str) -> list:
    """Analyze all categories and return items list."""
    id_map = {str(v.get('id')): v for v in videos}
    items = []
    
    try:
        llm_client = get_default_client()
        print(f"Using LLM: {llm_client.get_model_name()}")
    except LLMConfigError as e:
        raise ValueError(f"Failed to initialize LLM client: {e}")

    for cat in ["ai视频玩法", "ai工具滤镜", "ai图像玩法"]:
        ids = category_map.get(cat, [])
        vids = [id_map[i] for i in ids if i in id_map]

        if vids:
            print(f"\nAnalyzing {cat} ({len(vids)} videos)...")
            item = analyze_category(llm_client, prompt_template, cat, vids)
        else:
            print(f"\n{cat}: No videos, using fallback")
            item = {
                "category_tag": cat,
                "trend_title": f"{cat} - 暂无显著新热点",
                "core_data": "本周期暂无明显爆款",
                "background": "该分类在本周期样本不足，暂未形成可复用热点叙事。",
                "ua_suggestion": "可继续观察24小时并补充样本",
                "product_benchmark": normalize_product_benchmark(cat, "", ["保持常规素材迭代"]),
                "risk_notes": ["常规合规风险"],
                "trend_stage": {"label": "已过峰值", "reason": "样本不足或热度走低"},
                "reference_links": [],
                "representative_videos": []
            }

        # Add reference links and representative videos
        refs = []
        reps = []
        for v in sorted(vids, key=lambda x: int(x.get('playCount') or 0), reverse=True):
            url = v.get('videoMeta', {}).get('webVideoUrl') or f"https://www.tiktok.com/@user/video/{v.get('id')}"
            likes = int(v.get('diggCount') or 0)
            views = int(v.get('playCount') or 0)
            days_ago = calculate_days_ago(v)

            refs.append({"url": url, "diggCount": likes, "playCount": views, "daysAgo": days_ago})
            reps.append({
                "id": str(v.get('id')),
                "title": v.get('text', '')[:80],
                "author": v.get('authorMeta', {}).get('nickName', 'unknown'),
                "likes": likes,
                "views": views,
                "days_ago": days_ago,
                "url": url,
                "video_summary": v.get('video_summary', '')
            })

        item["reference_links"] = refs
        item["representative_videos"] = reps
        items.append(item)
    
    return items


def analyze_with_retry(videos: list, category_map: dict, prompt_template: str, max_retries: int = 3) -> list:
    """Analyze with retry logic."""
    for attempt in range(1, max_retries + 1):
        print(f"\n{'='*50}")
        print(f"Analysis attempt {attempt}/{max_retries}")
        print(f"{'='*50}")
        
        try:
            items = analyze_all_categories(videos, category_map, prompt_template)
            print(f"\n✅ Analysis complete: {len(items)} categories")
            return items
            
        except LLMRateLimitError as e:
            print(f"⚠️ Rate limit: {e}")
            if attempt < max_retries:
                import time
                time.sleep(5 * attempt)
            else:
                notified = push_error_notification(f"Phase 2 Analysis failed (attempt {attempt}/{max_retries})\n{e}")
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
                notified = push_error_notification(f"Phase 2 Analysis failed after {max_retries} retries\n{e}")
                if not notified:
                    print("⚠️ Warning: Failed to send Feishu error notification")
                raise
    
    raise Exception(f"Analysis failed after {max_retries} attempts")


def main():
    parser = argparse.ArgumentParser(description='Phase 2 Step 2: Analyze categories')
    parser.add_argument('--category-map', '-c', type=str, required=True,
                        help='Input category_map.json from classification step')
    parser.add_argument('--output', '-o', type=str, required=True,
                        help='Output file for report.json')
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
    report = build_report(videos, category_map, items)
    
    # Save output
    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Report saved to: {output_file}")
    print(f"   Valid videos: {report['valid_hot_count']}")
    print(f"   Trends generated: {len(report['items'])}")
    sys.exit(0)


if __name__ == "__main__":
    main()
