#!/usr/bin/env python3
"""
TikTok AI 趋势日报 - 写入飞书多维表格

将 tiktok-feishu-radar 生成的 report.json 写入到飞书多维表格
目标表格: TikTok AI 趋势日报 (app_token: O76YbeXDwaom4Osgd3ScfUx2nAK)

使用方式:
    python3 scripts/write_bitable.py --report skill_runs/<timestamp>/report.json

字段映射:
- 视频编号 → video_id (主字段)
- TikTok AI 趋势日报 → 趋势标题
- 趋势类型 → category_tag
- 核心数据 → core_data
- 背景 → background
- 对标点 → product_benchmark
- UA建议 → ua_suggestion
- 参考链接1-5 → reference_links
- 监控周期 → period_hours + time_range
- 生成时间 → generated_at
"""

import json
import argparse
import time
import requests
from pathlib import Path
from datetime import datetime


# ============================================================
# 配置 - 目标多维表格
# ============================================================
# BITABLE_APP_TOKEN 从 .env 读取（键名：BITABLE_APP_TOKEN）
BITABLE_TABLE_ID = "tblaSRVLJafzmzoc"

# 飞书应用凭证 (从环境变量读取)
import os

# 先尝试加载 .env 文件
SCRIPT_DIR = Path(__file__).resolve().parent
ENV_FILE = SCRIPT_DIR / ".env"

def load_env(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

load_env(ENV_FILE)

BITABLE_APP_TOKEN = os.environ.get("BITABLE_APP_TOKEN", "")
APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")

# Token 缓存
_bitable_token_cache = {"token": None, "expire_at": 0}


# ============================================================
# 工具函数
# ============================================================

def get_bitable_token():
    """获取 tenant_access_token (有效期2小时，自动缓存刷新)"""
    now_ts = time.time()
    if _bitable_token_cache["token"] and _bitable_token_cache["expire_at"] > now_ts + 60:
        return _bitable_token_cache["token"]

    try:
        resp = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": APP_ID, "app_secret": APP_SECRET},
            timeout=10,
        )
        data = resp.json()
        if data.get("code") == 0:
            token = data["tenant_access_token"]
            expire = data.get("expire", 7200)
            _bitable_token_cache["token"] = token
            _bitable_token_cache["expire_at"] = now_ts + expire
            print(f"[TOKEN] 获取成功 (有效期 {expire}s)")
            return token
        else:
            print(f"[TOKEN] 获取失败: {data}")
            return None
    except Exception as e:
        print(f"[TOKEN] 获取异常: {e}")
        return None


def fmt_number(num):
    """格式化数字: 1500000 -> 1.5M, 50000 -> 50K"""
    if num is None or num == 0:
        return "0"
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num/1000:.1f}K"
    return str(num)


def build_reference_links(ref_links, video_url=None):
    """
    构建参考链接字段
    - For per-video reports: single "参考链接" field with video_url
    - For category reports: multiple "参考链接{i}" fields
    """
    # If video_url is provided (per-video mode), use single field
    if video_url:
        return {
            "参考链接": {"text": "查看视频", "link": video_url}
        }
    
    # Category mode: multiple numbered links
    links = {}
    for i, link in enumerate(ref_links[:5], 1):
        if isinstance(link, dict):
            url = link.get('url', '')
            play = link.get('playCount', 0)
            digg = link.get('diggCount', 0)
            days = link.get('daysAgo', 0)
            text = f"视频{i} {days}天 | 👍{fmt_number(digg)} 👀{fmt_number(play)}"
        else:
            url = link
            text = f"参考{i}"
        
        if url:
            links[f"参考链接{i}"] = {"text": text, "link": url}
    
    return links


def build_record_fields(item, metadata):
    """将 report item 转换为多维表格字段"""
    
    category_tag = item.get('category_tag', '')
    trend_title = item.get('trend_title', '')
    
    # 检测是否为 per-video 报告 (有 video_id 字段)
    is_per_video = 'video_id' in item
    
    # 构建标题
    if is_per_video:
        # Per-video: 直接使用趋势标题
        title = trend_title
    else:
        # Category: 格式为 [分类] 趋势标题
        title = f"{category_tag} - {trend_title}"
    
    # 产品对标点 (数组 → 字符串)
    benchmarks = item.get('product_benchmark', [])
    if isinstance(benchmarks, list):
        benchmarks_str = '\n'.join(f"- {b}" for b in benchmarks if b)
    else:
        benchmarks_str = str(benchmarks)
    
    # UA建议
    ua_suggestion = item.get('ua_suggestion', '')
    
    # 参考链接
    ref_links = item.get('reference_links', [])
    video_url = item.get('video_url') if is_per_video else None
    ref_links_dict = build_reference_links(ref_links, video_url=video_url)
    
    # 风险提示
    risks = item.get('risk_notes', [])
    if isinstance(risks, list):
        risks_str = '\n'.join(f"- {r}" for r in risks if r)
    else:
        risks_str = str(risks)

    # 推送日期 (Feishu date field needs Unix timestamp in milliseconds)
    generated_at = metadata.get('generated_at', '')
    push_date_ts = 0
    if generated_at:
        from datetime import datetime
        try:
            push_date_ts = int(datetime.strptime(generated_at, "%Y-%m-%d %H:%M:%S").timestamp() * 1000)
        except Exception:
            push_date_ts = 0

    fields = {
        "视频编号": item.get('video_id', ''),
        "TikTok AI 趋势日报": title,
        "趋势类型": category_tag,
        "核心数据": item.get('core_data', ''),
        "背景": item.get('background', ''),
        "对标点": benchmarks_str,
        "UA建议": ua_suggestion,
        "监控周期": metadata.get('time_range', ''),
        "推送日期": push_date_ts,
        "风险提示": risks_str,
    }
    
    # 添加参考链接 (per-video 为单字段 "参考链接", category 为多字段 "参考链接{i}")
    fields.update(ref_links_dict)
    
    return fields


def fetch_existing_video_id_map(token):
    """
    拉取表格中按推送日期倒序的前100条记录，建立「视频编号」→「record_id」映射。

    使用 search API (POST): sort=[{field_name: "推送日期", desc: true}]
    - 推送日期是 DateTime 字段，search API 支持对其正确排序
    - 格式为标准 JSON，不存在 URL 编码问题
    - 取前100条（表格共120条，最旧的10条在批次外）
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    url = (
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/"
        f"{BITABLE_APP_TOKEN}/tables/{BITABLE_TABLE_ID}/records/search"
    )

    video_id_to_record_id = {}

    try:
        body = {
            "page_size": 100,
            "automatic_fields": True,
            "sort": [{"field_name": "推送日期", "desc": True}],
            "filter": {
                "conjunction": "and",
                "conditions": [
                    {"field_name": "视频编号", "operator": "isNotEmpty", "value": []},
                ],
            },
        }
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        result = resp.json()

        if result.get("code") != 0:
            print(f"[WARN] 拉取现有记录失败: code={result.get('code')} msg={result.get('msg')}")
            return video_id_to_record_id

        # search API 在无文本搜索时 page_size 不严格限制，取前100条
        all_records = result.get("data", {}).get("items", [])
        records = all_records[:100]
        total = result.get("data", {}).get("total", len(all_records))

        print(f"[INFO] 拉取到 {len(records)} 条记录 (表格共 {total} 条)")

        for record in records:
            fields = record.get("fields", {})
            video_id_raw = fields.get("视频编号", "")
            # 视频编号可能是字符串或 rich text 数组
            if isinstance(video_id_raw, list):
                video_id = video_id_raw[0].get("text", "") if video_id_raw else ""
            else:
                video_id = video_id_raw

            if video_id:
                video_id_to_record_id[str(video_id)] = record["record_id"]

        print(f"[INFO] 其中 {len(video_id_to_record_id)} 条有视频编号")

        # Debug: 显示前5条的 record_id、推送日期和视频编号
        for record in records[:5]:
            vid_raw = record.get("fields", {}).get("视频编号", "")
            vid = vid_raw[0].get("text", "") if isinstance(vid_raw, list) else vid_raw
            rid = record.get("record_id", "")
            pd = record.get("fields", {}).get("推送日期", "")
            pd_str = datetime.fromtimestamp(pd / 1000).strftime("%Y-%m-%d %H:%M:%S") if pd else "?"
            print(f"[DEBUG] record_id={rid}, push_date={pd_str}, video_id={vid}")

    except Exception as e:
        print(f"[WARN] 拉取现有记录异常: {e}")

    return video_id_to_record_id


def write_to_bitable(report):
    """将 report 写入多维表格（upsert 语义：已存在则更新，不存在则新建）"""
    token = get_bitable_token()
    if not token:
        print("[ERROR] 无法获取 token")
        return 0

    # 拉取推送日期最新的100条记录，建立 video_id → record_id 映射
    existing_map = fetch_existing_video_id_map(token)

    # 构建报告项 → 字段
    metadata = {
        'time_range': report.get('time_range', ''),
        'generated_at': report.get('generated_at', ''),
    }

    to_create = []   # 新记录
    to_update = []   # 更新记录 (record_id + fields)

    for item in report.get('items', []):
        video_id = str(item.get('video_id', ''))
        fields = build_record_fields(item, metadata)

        if video_id and video_id in existing_map:
            # 已存在 → 更新
            to_update.append({
                "record_id": existing_map[video_id],
                "fields": fields,
            })
        else:
            # 不存在 → 新建
            to_create.append({"fields": fields})

    total = len(to_create) + len(to_update)
    print(f"[INFO] 共 {total} 条记录（新建 {len(to_create)} / 更新 {len(to_update)}）")

    written = 0

    # 批量新建
    if to_create:
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{BITABLE_TABLE_ID}/records/batch_create"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        try:
            resp = requests.post(url, headers=headers, json={"records": to_create}, timeout=30)
            result = resp.json()
            if result.get("code") == 0:
                created = len(result.get("data", {}).get("records", []))
                print(f"[OK] 新建成功: {created} 条")
                written += created
            else:
                print(f"[FAIL] 新建失败: {result}")
        except Exception as e:
            print(f"[ERROR] 新建异常: {e}")

    # 批量更新
    if to_update:
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{BITABLE_TABLE_ID}/records/batch_update"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        try:
            resp = requests.post(url, headers=headers, json={"records": to_update}, timeout=30)
            result = resp.json()
            if result.get("code") == 0:
                updated = len(result.get("data", {}).get("records", []))
                print(f"[OK] 更新成功: {updated} 条")
                written += updated
            else:
                print(f"[FAIL] 更新失败: {result}")
        except Exception as e:
            print(f"[ERROR] 更新异常: {e}")

    return written


def main():
    parser = argparse.ArgumentParser(description="TikTok AI 趋势日报 - 写入飞书多维表格")
    parser.add_argument("--report", required=True, help="report.json 文件路径")
    args = parser.parse_args()

    # 读取 report.json
    report_path = Path(args.report)
    if not report_path.exists():
        print(f"[ERROR] 文件不存在: {report_path}")
        return

    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    print(f"📊 读取报告: {report.get('title', 'Unknown')}")
    print(f"   趋势数量: {len(report.get('items', []))}")
    print(f"   生成时间: {report.get('generated_at', '')}")
    print()
    print("📤 正在写入多维表格 (upsert 模式: 已存在则更新，不存在则新建)...")

    written = write_to_bitable(report)
    print(f"\n✅ 完成! 共处理 {written} 条记录")


if __name__ == "__main__":
    main()
