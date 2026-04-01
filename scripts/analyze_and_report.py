#!/usr/bin/env python3
"""
TikTok Video Analyzer using LLM API
Analyzes TikTok videos and generates structured report JSON

Workflow:
1. Load filtered-result.json with video data + summaries
2. Load prompt template from prompt_for_minimax.txt
3. Call LLM API for analysis (MiniMax or OpenRouter)
4. Save report.json
"""

import sys
import json
import re
import time
from pathlib import Path
from datetime import datetime

# Add script directory to path for imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# LLM Client imports (new interface)
from llm_factory import get_default_client
from llm_client import LLMClient, LLMError, LLMRateLimitError, LLMConfigError

# Shared utilities
from utils import calculate_days_ago, summarize_video_time_window

# Configuration
BASE_DIR = SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "trend-scrap" / "tiktok-scraper" / "data"
RESULT_FILE = DATA_DIR / "filtered-result.json"
PROMPT_FILE = BASE_DIR / "references" / "prompt_for_minimax.txt"


def load_results():
    """Load filtered-result.json"""
    if not RESULT_FILE.exists():
        raise FileNotFoundError(f"Result file not found: {RESULT_FILE}")

    with open(RESULT_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)



def load_prompt():
    """Load prompt template"""
    if not PROMPT_FILE.exists():
        raise FileNotFoundError(f"Prompt file not found: {PROMPT_FILE}")
    
    with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
        return f.read()


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
    
    # Build TikTok URL
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
    # Try to find JSON block in response
    # Look for markdown code blocks
    json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find any JSON object
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            raise Exception("Could not find JSON in response")

    # Parse JSON
    return json.loads(json_str)


def classify_video_category(video):
    """Heuristic fallback classifier for unassigned videos."""
    text = " ".join([
        str(video.get('text', '')),
        str(video.get('desc', '')),
        str(video.get('video_summary', '')),
    ]).lower()

    tool_keywords = [
        "filter", "滤镜", "effect", "特效", "tool", "工具", "app", "website", "prompt"
    ]
    image_keywords = [
        "image", "photo", "照片", "图片", "avatar", "portrait", "midjourney", "stable diffusion", "绘画"
    ]

    if any(k in text for k in tool_keywords):
        return "ai工具滤镜"
    if any(k in text for k in image_keywords):
        return "ai图像玩法"
    return "ai视频玩法"


def ai_classify_videos(llm_client: LLMClient, system_prompt: str, results):
    """Step 1: Ask AI to classify every video into 3 fixed categories."""
    videos_text = ""
    for i, video in enumerate(results, 1):
        videos_text += format_video_for_prompt(video, i)

    prompt = f"""你现在只做分类，不做趋势分析。
将以下视频按内容分到3个固定分类：
- ai视频玩法
- ai工具滤镜
- ai图像玩法

要求：
1. 输出严格JSON，不要markdown
2. 每个视频ID必须且只能出现一次
3. 只使用下面给出的ID

输出格式：
{{
  "ai视频玩法": ["id1", "id2"],
  "ai工具滤镜": ["id3"],
  "ai图像玩法": ["id4", "id5"]
}}

视频数据：
{videos_text}
"""
    print(f"  Calling {llm_client.get_model_name()} for classification...")
    text = llm_client.call(system_prompt, prompt)
    raw = parse_json_from_response(text)

    categories = {"ai视频玩法": [], "ai工具滤镜": [], "ai图像玩法": []}
    valid_ids = {str(v.get('id')) for v in results}
    used = set()

    for cat in categories.keys():
        ids = raw.get(cat, []) if isinstance(raw, dict) else []
        if not isinstance(ids, list):
            ids = []
        for vid in ids:
            s = str(vid)
            if s in valid_ids and s not in used:
                categories[cat].append(s)
                used.add(s)

    # fallback: unassigned videos go to heuristic category
    for v in results:
        vid = str(v.get('id'))
        if vid not in used:
            categories[classify_video_category(v)].append(vid)
            used.add(vid)

    return categories


def normalize_product_benchmark(category, ua_suggestion, points):
    """Force product benchmark to required sentence template."""
    if not isinstance(points, list):
        points = []

    def make_fallback():
        effect = "视频特效" if category == "ai视频玩法" else "图片特效"
        upload = "1-2张人物/宠物照片" if category != "ai工具滤镜" else "1张自拍或场景图"
        result = "剧情化短视频" if category == "ai视频玩法" else ("风格化图像" if category == "ai图像玩法" else "滤镜化效果视频")
        attraction = "低门槛一键生成、强视觉反差、便于社媒传播"
        return f"Guru 可以出一个【{effect}】玩法，用户上传【{upload}】，生成【{result}】。这个玩法的吸引力在于【{attraction}】"

    normalized = []
    for p in points:
        s = str(p).strip()
        if s.startswith("Guru 可以出一个【") and "用户上传【" in s and "生成【" in s and "吸引力在于【" in s:
            normalized.append(s)
    if not normalized:
        normalized = [make_fallback()]
    return normalized[:3]


def ai_analyze_one_category(llm_client: LLMClient, system_prompt: str, category: str, videos):
    """Step 2: Ask AI to analyze one category only (no links)."""
    videos_text = ""
    for i, video in enumerate(videos, 1):
        videos_text += format_video_for_prompt(video, i)

    prompt = f"""你是UA分析师。仅分析分类：{category}

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
"""
    print(f"  Calling {llm_client.get_model_name()} for {category} analysis...")
    text = llm_client.call(system_prompt, prompt)
    data = parse_json_from_response(text)

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


def analyze_videos():
    """Two-step analysis: AI classification -> per-category AI analysis -> code-generated links."""
    
    # Initialize LLM client via factory
    try:
        llm_client = get_default_client()
        print(f"Using LLM: {llm_client.get_model_name()}")
    except LLMConfigError as e:
        raise ValueError(f"Failed to initialize LLM client: {e}")

    print(f"\nLoading data...")
    results = load_results()

    prompt_template = load_prompt()
    print(f"  - Found {len(results)} videos")

    if not results:
        raise ValueError("No videos found in filtered-result.json")

    period_hours, time_range = summarize_video_time_window(results)

    # Step 1: classify
    print("\nStep 1/2: AI classifying videos...")
    category_map = ai_classify_videos(llm_client, prompt_template, results)

    id_map = {str(v.get('id')): v for v in results}
    items = []

    # Step 2: analyze each category separately
    print("Step 2/2: AI analyzing each category...")
    for cat in ["ai视频玩法", "ai工具滤镜", "ai图像玩法"]:
        ids = category_map.get(cat, [])
        vids = [id_map[i] for i in ids if i in id_map]

        if vids:
            item = ai_analyze_one_category(llm_client, prompt_template, cat, vids)
        else:
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

        # code-generated links and representative videos (ALL videos in category)
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

    report = {
        "title": "TikTok AI玩法日报",
        "platform": "TikTok",
        "topic": "AI玩法",
        "period_hours": period_hours,
        "time_range": time_range,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "valid_hot_count": len(results),
        "trend_overview": "基于分类后的视频样本自动生成三类趋势分析。",
        "items": items,
        "category_map": category_map
    }

    return report

def save_report(report, output_file):
    """Save report to file"""
    # Create output directory if needed
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"Report saved to: {output_file}")


def validate_report(report: dict) -> tuple[bool, str]:
    """
    Validate that the report has exactly 3 valid categories.
    
    Returns:
        (is_valid, error_message)
    """
    valid_categories = {"ai视频玩法", "ai工具滤镜", "ai图像玩法"}
    
    items = report.get('items', [])
    if len(items) != 3:
        return False, f"Expected 3 categories, got {len(items)}"
    
    found_categories = set()
    for item in items:
        cat = item.get('category_tag', '')
        if cat not in valid_categories:
            return False, f"Invalid category: {cat}"
        found_categories.add(cat)
    
    if len(found_categories) != 3:
        return False, f"Expected 3 unique categories, found: {found_categories}"
    
    return True, "OK"


def analyze_with_retry(max_retries: int = 3) -> dict:
    """
    Run analysis with retry logic and validation.
    
    Args:
        max_retries: Maximum number of attempts
        
    Returns:
        Valid report dict
        
    Raises:
        Exception: If all retries fail
    """
    from feishu_notify import push_error_notification
    
    for attempt in range(1, max_retries + 1):
        print(f"\n{'='*50}")
        print(f"Analysis attempt {attempt}/{max_retries}")
        print(f"{'='*50}")
        
        try:
            report = analyze_videos()
            
            # Validate output
            is_valid, error_msg = validate_report(report)
            if is_valid:
                print(f"✅ Validation passed: {error_msg}")
                return report
            else:
                print(f"⚠️ Validation failed: {error_msg}")
                if attempt < max_retries:
                    print("Retrying...")
                    import time
                    time.sleep(2)  # Brief backoff
                continue
                
        except LLMRateLimitError as e:
            error_str = f"Rate limit exceeded (attempt {attempt}): {e}"
            print(f"⚠️ {error_str}")
            if attempt < max_retries:
                wait_time = 5 * attempt  # Progressive backoff
                print(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                notified = push_error_notification(f"Phase 2 API 调用失败 (尝试 {attempt}/{max_retries})\n{e}")
                if not notified:
                    print("⚠️ Warning: Failed to send Feishu error notification")
                raise
                
        except LLMError as e:
            error_str = f"LLM API error (attempt {attempt}): {e}"
            print(f"⚠️ {error_str}")
            if attempt < max_retries:
                print("Retrying...")
                time.sleep(2)
            else:
                notified = push_error_notification(f"Phase 2 API 调用失败 (尝试 {attempt}/{max_retries})\n{e}")
                if not notified:
                    print("⚠️ Warning: Failed to send Feishu error notification")
                raise
                
        except Exception as e:
            error_str = f"Unexpected error (attempt {attempt}): {e}"
            print(f"❌ {error_str}")
            import traceback
            traceback.print_exc()
            if attempt < max_retries:
                print("Retrying...")
                time.sleep(2)
            else:
                notified = push_error_notification(f"Phase 2 格式校验失败，已重试 {max_retries} 次\n{e}")
                if not notified:
                    print("⚠️ Warning: Failed to send Feishu error notification")
                raise
    
    # This shouldn't happen, but just in case
    raise Exception(f"Failed after {max_retries} attempts")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze TikTok videos with LLM API')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output file path (default: skill_runs/<timestamp>/report.json)')
    parser.add_argument('--max-retries', '-r', type=int, default=3,
                        help='Maximum retry attempts (default: 3)')
    args = parser.parse_args()
    
    try:
        # Run analysis with retry logic
        report = analyze_with_retry(max_retries=args.max_retries)
        
        # Determine output path
        if args.output:
            output_file = Path(args.output)
        else:
            # Default: skill_runs/<timestamp>/report.json
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = BASE_DIR / "skill_runs" / timestamp
            output_file = output_dir / "report.json"
        
        # Save report
        save_report(report, output_file)
        
        print(f"\n✅ Analysis complete!")
        print(f"   Valid videos: {report.get('valid_hot_count', 0)}")
        print(f"   Trends generated: {len(report.get('items', []))}")
        
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Analysis failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
