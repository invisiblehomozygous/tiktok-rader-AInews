#!/usr/bin/env python3
"""
Update prompt file with product manual content from Feishu Bitable

Reads the product manual from Feishu and updates the prompt file with product capabilities.
"""

import sys
import json
import requests
from pathlib import Path

# Add script directory to path for imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
from utils import load_env

# Configuration
BASE_DIR = SCRIPT_DIR.parent
PROMPT_FILE_MINIMAX = BASE_DIR / "references" / "prompt_for_minimax.txt"
PROMPT_FILE_PER_VIDEO = BASE_DIR / "references" / "prompt_for_each_video.txt"

# Feishu Bitable - 产品手册
WIKI_TOKEN = "V57ZwcrHwiNi40kn648cxXr5n3d"
APP_TOKEN = "MqoLb7Sydau0oEs5mMLcBcOenxg"
TABLE_ID = "tbliRtdmBidw3V2B"  # AI工具表


def get_tenant_access_token(app_id, app_secret):
    """Get Feishu tenant access token"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {"app_id": app_id, "app_secret": app_secret}
    
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    result = resp.json()
    
    if result.get("code") != 0:
        raise Exception(f"Failed to get token: {result}")
    
    return result["tenant_access_token"]


def read_bitable_records(token, app_token, table_id):
    """Read records from Feishu Bitable"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.get(url, headers=headers, timeout=30)
    result = resp.json()
    
    if result.get("code") != 0:
        raise Exception(f"Failed to read bitable: {result}")
    
    return result.get("data", {}).get("items", [])


def format_product_manual(records):
    """Format product manual content for the prompt"""
    lines = ["# 产品手册\n"]
    lines.append("以下是 Guru 现有产品能力，请基于这些产品提产品对标建议：\n")
    
    # Filter for AI Image and AI Video products
    image_products = []
    video_products = []
    filter_products = []
    other_products = []
    
    for record in records:
        fields = record.get("fields", {})
        name = fields.get("名称", "")
        category = fields.get("分类", [])
        description = fields.get("产品描述", "")
        competitors = fields.get("竞品", {})
        
        if not name:
            continue
        
        # Format competitors - handle different types
        competitors_text = ""
        if isinstance(competitors, dict):
            competitors_text = competitors.get("text", "")
        elif isinstance(competitors, list):
            # Handle list of dicts or strings
            if competitors and isinstance(competitors[0], dict):
                competitors_text = ", ".join([c.get("text", "") for c in competitors if isinstance(c, dict)])
            else:
                competitors_text = ", ".join([str(c) for c in competitors])
        
        product_info = f"- **{name}**: {description}"
        if competitors_text:
            product_info += f" | 竞品: {competitors_text}"
        
        # Categorize by type
        category_str = ""
        if isinstance(category, list):
            category_str = ",".join([str(c) for c in category])
        elif isinstance(category, str):
            category_str = category
        
        if "图像" in category_str:
            image_products.append(product_info)
        elif "视频" in category_str:
            video_products.append(product_info)
        elif "聊天" in category_str or "工具" in category_str:
            filter_products.append(product_info)
        else:
            other_products.append(product_info)
    
    if image_products:
        lines.append("## 图像类产品\n")
        lines.extend([p + "\n" for p in image_products])
        lines.append("\n")
    
    if video_products:
        lines.append("## 视频类产品\n")
        lines.extend([p + "\n" for p in video_products])
        lines.append("\n")
    
    if filter_products:
        lines.append("## 滤镜/工具类产品\n")
        lines.extend([p + "\n" for p in filter_products])
        lines.append("\n")
    
    if other_products:
        lines.append("## 其他产品\n")
        lines.extend([p + "\n" for p in other_products])
        lines.append("\n")
    
    return "".join(lines)


def update_prompt_file(prompt_file: Path, product_manual_content: str):
    """Update the prompt file with product manual content (replace, never append duplicates)."""
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

    # Read existing prompt
    with open(prompt_file, 'r', encoding='utf-8') as f:
        prompt_content = f.read()

    # Normalize manual content
    product_manual_content = product_manual_content.strip() + "\n"

    # Robust replacement strategy:
    # Replace from the LAST occurrence of product-manual heading to EOF.
    # This avoids repeated append growth across runs.
    heading_variants = ["# 产品手册", "#产品手册"]
    start_idx = -1
    for h in heading_variants:
        idx = prompt_content.rfind(h)
        if idx > start_idx:
            start_idx = idx

    if start_idx >= 0:
        # Keep prompt before manual section, replace manual section fully
        prefix = prompt_content[:start_idx].rstrip() + "\n\n"
        prompt_content = prefix + product_manual_content
    else:
        # No manual section found: append once
        prompt_content = prompt_content.rstrip() + "\n\n" + product_manual_content

    # Write back
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write(prompt_content)

    print(f"✅ Prompt file updated: {prompt_file}")


def main():
    try:
        # Load Feishu credentials
        env_vars = load_env()
        app_id = env_vars.get("FEISHU_APP_ID", "")
        app_secret = env_vars.get("FEISHU_APP_SECRET", "")
        
        if not app_id or not app_secret:
            raise ValueError("FEISHU_APP_ID or FEISHU_APP_SECRET not found in .env")
        
        print("📖 Reading product manual from Feishu...")
        
        # Get token
        token = get_tenant_access_token(app_id, app_secret)
        
        # Read records
        records = read_bitable_records(token, APP_TOKEN, TABLE_ID)
        print(f"   Found {len(records)} product records")
        
        # Format product manual
        product_manual = format_product_manual(records)
        
        # Update both prompt files
        print("\n📝 Updating prompt files...")
        update_prompt_file(PROMPT_FILE_MINIMAX, product_manual)
        update_prompt_file(PROMPT_FILE_PER_VIDEO, product_manual)
        
        print("\n✅ Product manual update complete!")
        print(f"   Updated: {PROMPT_FILE_MINIMAX.name}")
        print(f"   Updated: {PROMPT_FILE_PER_VIDEO.name}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
