#!/usr/bin/env python3
"""
Build Feishu card payload from TikTok trend report.

IMPORTANT: When adding links in card content:
- Use Markdown link format: [text](url) 
- DO NOT use {"tag": "a", "href": url, "text": text} directly
- Feishu server will automatically convert Markdown links to clickable a tags
- Using a tag directly in JSON will cause 400 parse error
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

from utils import summarize_video_time_window


def md_list(items, bullet="- "):
    if isinstance(items, str):
        return items
    return "\n".join(f"{bullet}{x}" for x in items if str(x).strip())


def fmt_number(num):
    """Format number to K/M format."""
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    elif num >= 1000:
        return f"{num/1000:.1f}K"
    return str(num)


def classify_video_category(video):
    text = " ".join([
        str(video.get('text', '')),
        str(video.get('desc', '')),
        str(video.get('video_summary', '')),
    ]).lower()

    if any(k in text for k in ["filter", "滤镜", "effect", "特效", "tool", "工具", "app", "website", "prompt"]):
        return "ai工具滤镜"
    if any(k in text for k in ["image", "photo", "照片", "图片", "avatar", "portrait", "midjourney", "stable diffusion", "绘画"]):
        return "ai图像玩法"
    return "ai视频玩法"


def fmt_links(links, representative_videos=None, raw_videos=None):
    """Format reference links with new format: 视频n x天 | 👍291.5K 👀5.9M
    Use Markdown link format [text](url) - Feishu will convert to a tags automatically
    """
    from datetime import datetime, timezone, timedelta
    
    # 计算当前时间（UTC+8）
    now = datetime.now(timezone(timedelta(hours=8)))
    
    # 构建 video_id -> raw_data 的映射
    raw_map = {}
    if raw_videos:
        for v in raw_videos:
            raw_map[v.get('id')] = v
    
    parts = []
    
    # Use representative_videos if available, otherwise fall back to links
    if representative_videos:
        for i, video in enumerate(representative_videos or [], 1):
            if not video:
                continue
            url = video.get('url', '')
            if not url and links and i <= len(links):
                url = links[i-1] if isinstance(links[i-1], str) else links[i-1].get('url', '')
            
            likes = video.get('likes', video.get('diggCount', 0))
            views = video.get('views', video.get('playCount', 0))
            days_ago = video.get('days_ago', video.get('daysAgo', None))
            
            # 如果没有 days_ago，尝试从 raw_videos 中获取
            if days_ago is None:
                video_id = video.get('id')
                raw_video = raw_map.get(str(video_id), {})
                create_time_iso = raw_video.get('createTimeISO')
                if create_time_iso:
                    try:
                        # createTimeISO 格式: 2026-03-14T05:10:56.000Z
                        # 简单解析：提取日期部分，手动计算
                        date_str = create_time_iso.split('T')[0]  # 2026-03-14
                        video_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        today = now.date()
                        days_ago = (today - video_date).days
                    except:
                        days_ago = 0
                else:
                    days_ago = 0
            
            if isinstance(likes, str):
                likes_display = likes
            else:
                likes_display = fmt_number(likes) if likes else "0"
                
            if isinstance(views, str):
                views_display = views
            else:
                views_display = fmt_number(views) if views else "0"
            
            text = f"视频{i} {days_ago}天 | 👍{likes_display} 👀{views_display}"
            
            if url:
                # Use Markdown link format - Feishu will convert to a tag automatically
                parts.append(f"[{text}]({url})")
            else:
                parts.append(text)
    else:
        for i, link in enumerate(links or [], 1):
            if not link:
                continue
            if isinstance(link, str):
                parts.append(f"[参考{i}]({link})")
            else:
                url = link.get('url', '')
                playCount = link.get('playCount', 0)
                diggCount = link.get('diggCount', 0)
                daysAgo = link.get('daysAgo', 0)
                text = f"视频{i} {daysAgo}天 | 👍{fmt_number(diggCount)} 👀{fmt_number(playCount)}"
                parts.append(f"[{text}]({url})")
    
    return "\n".join(parts) if parts else "无"


def fmt_field(value):
    """Format a field that could be either a string or an array."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " / ".join(str(x) for x in value if str(x).strip())
    return str(value) if value else "暂无"


def build_item_block(item, raw_videos=None, category_map=None):
    stage = item.get("trend_stage", {}) or {}
    benchmarks = item.get("product_benchmark", []) or []
    risks = item.get("risk_notes", []) or []

    # Hard guarantee: show ALL links by AI classification result (category_map)
    category = item.get('category_tag', '未分类')
    rep_videos = item.get('representative_videos', [])
    ref_links = item.get('reference_links', [])
    if raw_videos and category_map:
        raw_map = {str(v.get('id')): v for v in raw_videos}
        ids = category_map.get(category, []) or []
        grouped = [raw_map[i] for i in ids if i in raw_map]
        grouped = sorted(grouped, key=lambda x: int(x.get('playCount') or 0), reverse=True)
        rep_videos = [{
            'id': str(v.get('id')),
            'title': v.get('text', '')[:80],
            'author': v.get('authorMeta', {}).get('nickName', 'unknown'),
            'likes': int(v.get('diggCount') or 0),
            'views': int(v.get('playCount') or 0),
            'url': v.get('videoMeta', {}).get('webVideoUrl') or f"https://www.tiktok.com/@user/video/{v.get('id')}"
        } for v in grouped]
        ref_links = [{
            'url': rv['url'],
            'diggCount': rv['likes'],
            'playCount': rv['views']
        } for rv in rep_videos]

    lines = [
        f"**🏷️ [{category}] {item.get('trend_title', '未命名趋势')}**",
        f"**📊 核心数据摘要**\n{item.get('core_data', '暂无')}",
        f"**🧠 背景**\n{item.get('background', '暂无')}",
        f"**🎯 UA建议**\n{item.get('ua_suggestion', '暂无')}",
        f"**🧩 产品对标点**\n{md_list(benchmarks) if benchmarks else '- 暂无'}",
        f"**⚠️ 风险提示**\n{md_list(risks) if risks else '- 当前玩法风险较低，注意常规版权与隐私提示即可'}",
        f"**📈 趋势阶段判断**\n{stage.get('label', '待判断')}：{stage.get('reason', '暂无')}",
        f"**🔗 参考链接**\n{fmt_links(ref_links, rep_videos, raw_videos)}",
    ]
    return "\n\n".join(lines)


def build_card(report, raw_videos=None):
    title = f"{report.get('platform', 'TikTok')} {report.get('topic', 'AI玩法')} 日报"
    period_hours = report.get("period_hours", 0)
    time_range = report.get("time_range", "未提供")
    if raw_videos:
        computed_hours, computed_range = summarize_video_time_window(raw_videos)
        if computed_range != "Unknown":
            period_hours = computed_hours
            time_range = computed_range

    period_suffix = f"（跨度约 {period_hours} 小时）" if period_hours else ""
    metadata = (
        f"**📌 Metadata**\n"
        f"- 监控平台：{report.get('platform', 'TikTok')}\n"
        f"- 监控周期：{time_range}{period_suffix}\n"
        f"- 有效高优爆款：{report.get('valid_hot_count', len(report.get('items', [])))} 条\n"
        f"- 生成时间：{report.get('generated_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}"
    )
    overview = f"**🌟 趋势概览**\n{report.get('trend_overview', '暂无趋势概览')}"

    elements = [
        {"tag": "markdown", "content": metadata},
        {"tag": "hr"},
        {"tag": "markdown", "content": overview},
    ]

    category_map = report.get("category_map", {}) or {}
    for item in report.get("items", []):
        elements.append({"tag": "hr"})
        elements.append({"tag": "markdown", "content": build_item_block(item, raw_videos, category_map)})

    # 在卡片底部添加"查看多维表格"按钮
    elements.append({
        "tag": "action",
        "actions": [
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "📊 查看多维表格"},
                "type": "primary",
                "url": "https://bytedance.feishu.cn/base/O76YbeXDwaom4Osgd3ScfUx2nAK?table=tblaSRVLJafzmzoc&view=vewDQnhrTt",
            }
        ],
    })

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "purple",
            },
            "elements": elements,
        },
    }


def build_feishu_card(report_path: Path, raw_path: Path = None, output_path: Path = None) -> dict:
    """
    Build Feishu card from report.
    
    Args:
        report_path: Path to report.json
        raw_path: Optional path to filtered-result.json for days_ago calculation
        output_path: Optional path to write card JSON
        
    Returns:
        Card dictionary
    """
    report = json.loads(report_path.read_text(encoding="utf-8"))
    
    # Load raw video data if provided
    raw_videos = None
    if raw_path and raw_path.exists():
        raw_videos = json.loads(raw_path.read_text(encoding="utf-8"))
    
    card = build_card(report, raw_videos)
    
    if output_path:
        output_path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return card


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--raw", default=None, help="Path to raw filtered-result.json for calculating days_ago")
    args = ap.parse_args()

    card = build_feishu_card(
        report_path=Path(args.report),
        raw_path=Path(args.raw) if args.raw else None,
        output_path=Path(args.output)
    )
    print(args.output)


if __name__ == "__main__":
    main()
