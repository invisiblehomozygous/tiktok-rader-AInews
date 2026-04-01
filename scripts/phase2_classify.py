#!/usr/bin/env python3
"""
Phase 2 Step 1: Classify Videos

Classifies videos into 3 categories using LLM.
Outputs category_map.json for the analysis step.
"""

import argparse
import json
import sys
from pathlib import Path
import re

# Add script directory to path for imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from llm_factory import get_default_client
from llm_client import LLMClient, LLMError, LLMRateLimitError, LLMConfigError
from utils import calculate_days_ago, load_env


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


def classify_videos(llm_client: LLMClient, prompt_template: str, videos: list) -> dict:
    """
    Classify videos into 3 categories using LLM.
    
    Returns:
        {"ai视频玩法": ["id1", "id2"], "ai工具滤镜": [...], "ai图像玩法": [...]}
    """
    videos_text = ""
    for i, video in enumerate(videos, 1):
        videos_text += format_video_for_prompt(video, i)

    classification_prompt = f"""你现在只做分类，不做趋势分析。
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
    response = llm_client.call(prompt_template, classification_prompt)
    raw = parse_json_from_response(response)

    # Process and validate categories
    categories = {"ai视频玩法": [], "ai工具滤镜": [], "ai图像玩法": []}
    valid_ids = {str(v.get('id')) for v in videos}
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

    # Fallback: unassigned videos go to heuristic category
    for v in videos:
        vid = str(v.get('id'))
        if vid not in used:
            categories[classify_video_category(v)].append(vid)
            used.add(vid)

    return categories


def classify_with_retry(videos: list, prompt_template: str, max_retries: int = 3) -> dict:
    """Classify videos with retry logic."""
    try:
        llm_client = get_default_client()
        print(f"Using LLM: {llm_client.get_model_name()}")
    except LLMConfigError as e:
        raise ValueError(f"Failed to initialize LLM client: {e}")

    for attempt in range(1, max_retries + 1):
        print(f"\nClassification attempt {attempt}/{max_retries}")
        
        try:
            category_map = classify_videos(llm_client, prompt_template, videos)
            
            # Validate: should have at least some videos in each category
            total_classified = sum(len(vids) for vids in category_map.values())
            if total_classified == 0:
                raise ValueError("No videos were classified")
            
            print(f"✅ Classification complete: {total_classified} videos")
            for cat, vids in category_map.items():
                print(f"   {cat}: {len(vids)} videos")
            
            return category_map
            
        except LLMRateLimitError as e:
            print(f"⚠️ Rate limit: {e}")
            if attempt < max_retries:
                import time
                time.sleep(5 * attempt)
            else:
                raise
                
        except (LLMError, Exception) as e:
            print(f"⚠️ Error: {e}")
            if attempt < max_retries:
                import time
                time.sleep(2)
            else:
                raise
    
    raise Exception(f"Classification failed after {max_retries} attempts")


def main():
    parser = argparse.ArgumentParser(description='Phase 2 Step 1: Classify videos into categories')
    parser.add_argument('--output', '-o', type=str, required=True,
                        help='Output file for category_map.json')
    parser.add_argument('--max-retries', '-r', type=int, default=3,
                        help='Maximum retry attempts (default: 3)')
    args = parser.parse_args()
    
    # Load data
    if not RESULT_FILE.exists():
        print(f"ERROR: Result file not found: {RESULT_FILE}")
        sys.exit(1)
    
    with open(RESULT_FILE, 'r', encoding='utf-8') as f:
        videos = json.load(f)
    
    print(f"Loaded {len(videos)} videos")
    
    if not videos:
        print("ERROR: No videos to classify")
        sys.exit(1)
    
    # Load prompt template
    if not PROMPT_FILE.exists():
        print(f"ERROR: Prompt file not found: {PROMPT_FILE}")
        sys.exit(1)
    
    with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
        prompt_template = f.read()
    
    # Classify
    try:
        category_map = classify_with_retry(videos, prompt_template, args.max_retries)
    except Exception as e:
        print(f"ERROR: Classification failed: {e}")
        sys.exit(1)
    
    # Save output
    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(category_map, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Category map saved to: {output_file}")
    sys.exit(0)


if __name__ == "__main__":
    main()
