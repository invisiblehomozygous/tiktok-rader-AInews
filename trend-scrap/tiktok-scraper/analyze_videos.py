#!/usr/bin/env python3
"""
TikTok Video Analyzer using Memories.ai API
Analyzes TikTok videos and adds video_summary to filtered_result.json

Workflow:
1. Upload video via scraper_url (v1 API)
2. Poll for processing status
3. Get video_no
4. Generate summary via generate_summary (v1 API)
"""

import os
import sys
import json
import time
import requests
from pathlib import Path

# Configuration
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RESULT_FILE = DATA_DIR / "filtered-result.json"
ENV_FILE = BASE_DIR / ".env"

# Memories.ai API Configuration
MEMORIES_V1_BASE = "https://api.memories.ai/serve/api/v1"


def load_env():
    """Load environment variables from .env file"""
    env_vars = {}
    if ENV_FILE.exists():
        with open(ENV_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars


def load_results():
    """Load filtered_result.json"""
    if not RESULT_FILE.exists():
        raise FileNotFoundError(f"Result file not found: {RESULT_FILE}")
    
    with open(RESULT_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_results(data):
    """Save updated results to filtered_result.json"""
    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def upload_video(api_key: str, video_url: str, unique_id: str = "default") -> str:
    """Upload video via scraper_url and return task_id."""
    headers = {'Authorization': api_key}
    payload = {
        'video_urls': [video_url],
        'unique_id': unique_id
    }

    resp = requests.post(
        f"{MEMORIES_V1_BASE}/scraper_url",
        headers=headers,
        json=payload,
        timeout=120
    )
    result = resp.json()

    if not result.get('success'):
        raise Exception(f"Upload failed: {result.get('msg')}")

    task_id = result.get('data', {}).get('task_id') or result.get('data', {}).get('taskId')
    if not task_id:
        raise Exception("Upload succeeded but task_id missing")

    print("  Upload API: scraper_url")
    return task_id


def wait_for_video(api_key: str, task_id: str, unique_id: str = "default", max_wait: int = 300) -> str:
    """Wait for video to be processed and return video_no"""
    headers = {'Authorization': api_key}
    
    start_time = time.time()
    while time.time() - start_time < max_wait:
        resp = requests.get(
            f"{MEMORIES_V1_BASE}/get_video_ids_by_task_id",
            headers=headers,
            params={'task_id': task_id, 'unique_id': unique_id},
            timeout=30
        )
        result = resp.json()
        
        if not result.get('success'):
            raise Exception(f"Status check failed: {result.get('msg')}")
        
        videos = result['data']['videos']
        if videos:
            status = videos[0].get('status')
            print(f"  Video status: {status}")
            
            if status in ['PARSE', 'DONE', 'INDEXED', 'SUCCESS']:
                return videos[0].get('video_no')
        
        time.sleep(3)
    
    raise Exception("Timeout waiting for video processing")


def get_summary(api_key: str, video_no: str, unique_id: str = "default") -> str:
    """Get video summary using generate_summary API"""
    headers = {'Authorization': api_key}
    
    # Try CHAPTER type
    resp = requests.get(
        f"{MEMORIES_V1_BASE}/generate_summary",
        headers=headers,
        params={'video_no': video_no, 'type': 'CHAPTER', 'unique_id': unique_id},
        timeout=60
    )
    result = resp.json()
    
    if not result.get('success'):
        # Try topics if chapter fails
        resp = requests.get(
            f"{MEMORIES_V1_BASE}/generate_summary",
            headers=headers,
            params={'video_no': video_no, 'type': 'TOPIC', 'unique_id': unique_id},
            timeout=60
        )
        result = resp.json()
    
    if not result.get('success'):
        raise Exception(f"Summary failed: {result.get('msg')}")
    
    # Extract summary from result
    data = result.get('data', {})
    summary_text = data.get('summary', '')
    items = data.get('items', [])
    
    # Format the summary nicely
    if items:
        chapters = []
        for item in items:
            chapters.append(f"## {item.get('title', '')} ({item.get('start', '')}s)")
            chapters.append(f"{item.get('description', '')}\n")
        
        full_summary = summary_text + "\n\n" + "\n".join(chapters)
        return full_summary
    else:
        return summary_text


def get_video_url(video: dict) -> str:
    """Prefer canonical scraped URL; fallback to generic TikTok URL."""
    video_id = video.get('id', '')
    return (
        video.get('videoMeta', {}).get('webVideoUrl')
        or f"https://www.tiktok.com/@user/video/{video_id}"
    )


def analyze_video(api_key: str, video: dict, unique_id: str = "default") -> str:
    """Full workflow to analyze a video"""
    video_url = get_video_url(video)

    print(f"  Uploading: {video_url}")
    task_id = upload_video(api_key, video_url, unique_id)
    print(f"  Task ID: {task_id}")
    
    print("  Waiting for processing...")
    video_no = wait_for_video(api_key, task_id, unique_id)
    print(f"  Video No: {video_no}")
    
    print("  Generating summary...")
    summary = get_summary(api_key, video_no, unique_id)
    print(f"  Summary length: {len(summary)} chars")
    
    return summary


def process_videos():
    """Main processing function"""
    # Load config
    env_vars = load_env()
    api_key = env_vars.get("MEMORIES_API_KEY", "")

    if not api_key:
        raise ValueError("MEMORIES_API_KEY not found in .env file")

    # Load results
    print(f"\nLoading results from: {RESULT_FILE}")
    results = load_results()
    total = len(results)
    print(f"Found {total} videos")

    # Process videos in fixed batches: 5 + 5
    BATCH_SIZE = 5
    BATCH_GAP_SECONDS = 20

    updated_count = 0
    skipped_count = 0

    for batch_start in range(0, total, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total)
        batch_no = batch_start // BATCH_SIZE + 1
        print(f"\n--- Batch {batch_no}: videos {batch_start+1}-{batch_end} ---")

        for i in range(batch_start, batch_end):
            video = results[i]
            video_id = video.get('id', 'unknown')

            # Skip if already analyzed (and not an error)
            if 'video_summary' in video and video['video_summary'] and not str(video['video_summary']).startswith('ERROR'):
                print(f"\n[{i+1}/{total}] Skipping {video_id} (already analyzed)")
                skipped_count += 1
                continue

            print(f"\n[{i+1}/{total}] Processing {video_id}")

            try:
                summary = analyze_video(api_key, video)
                video['video_summary'] = summary
                updated_count += 1
            except Exception as e:
                print(f"  ERROR: {e}")
                video['video_summary'] = f"ERROR: {str(e)}"

            # Save progress after each video
            save_results(results)
            print(f"  Progress saved")

        # Wait 5 seconds between batches
        if batch_end < total:
            print(f"\nBatch {batch_no} complete. Waiting {BATCH_GAP_SECONDS}s before next batch...")
            time.sleep(BATCH_GAP_SECONDS)

    # Summary
    print(f"\n{'='*50}")
    print(f"Summary:")
    print(f"  - Updated: {updated_count}")
    print(f"  - Skipped: {skipped_count}")
    print(f"{'='*50}")


if __name__ == "__main__":
    try:
        process_videos()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
