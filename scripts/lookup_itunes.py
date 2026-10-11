"""
搜索/查询苹果播客，拿到节目 ID 和 RSS 地址，方便填进 config.yaml 的 itunes_id。

用法：
    python scripts/lookup_itunes.py 6 Minute English            # 按关键词搜索
    python scripts/lookup_itunes.py --id 262026947              # 按 ID 反查 RSS
    python scripts/lookup_itunes.py --id https://itunes.apple.com/lookup?id=262026947

说明：
    默认读取项目根目录 config.yaml 里的 proxy 配置（itunes.apple.com 国内可能需要代理），
    加 --no-proxy 可强制不走代理。
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.itunes import extract_itunes_id, lookup_feed_url, LOOKUP_URL
from modules.proxy_manager import create_httpx_client
from modules.config_loader import Config

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.yaml")

SEARCH_URL = "https://itunes.apple.com/search"


def load_proxy(config_path, no_proxy):
    if no_proxy or not os.path.exists(config_path):
        return None
    try:
        return Config(config_path).proxy_cfg
    except Exception as e:
        print(f"[WARN] 读取 {config_path} 失败，本次不使用代理: {e}")
        return None


def search(term, limit, proxy):
    """按关键词搜索播客，返回结果列表"""
    client = create_httpx_client(
        proxy_cfg=proxy,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with client:
        resp = client.get(SEARCH_URL, params={
            "term": term,
            "media": "podcast",
            "limit": limit,
        })
        resp.raise_for_status()
        return resp.json().get("results", [])


def print_result(idx, item):
    track_id = item.get("trackId")
    print(f"{idx}) {item.get('collectionName', '')}")
    print(f"   主播:     {item.get('artistName', '')}")
    print(f"   itunes_id: {track_id}")
    print(f"   RSS:      {item.get('feedUrl', '') or '(无)'}")
    print()


def main():
    parser = argparse.ArgumentParser(description="搜索/查询苹果播客的节目 ID 和 RSS 地址")
    parser.add_argument("term", nargs="*", help="搜索关键词，例如：6 Minute English")
    parser.add_argument("--id", dest="itunes_id",
                        help="按节目 ID（或 lookup 链接）反查 RSS 地址")
    parser.add_argument("--limit", type=int, default=10, help="搜索结果数量，默认 10")
    parser.add_argument("--no-proxy", action="store_true", help="不使用 config.yaml 里的代理")
    parser.add_argument("--config", default=CONFIG_PATH, help="配置文件路径")
    args = parser.parse_args()

    proxy = load_proxy(args.config, args.no_proxy)

    # 反查模式
    if args.itunes_id:
        parsed = extract_itunes_id(args.itunes_id)
        if not parsed:
            print(f"[ERROR] 无法解析 iTunes ID: {args.itunes_id}")
            return 1

        print(f"查询 {LOOKUP_URL}?id={parsed} ...")
        feed_url, err = lookup_feed_url(parsed, proxy=proxy)
        if not feed_url:
            print(f"[FAIL] {err}")
            return 1

        print(f"RSS: {feed_url}")
        print(f"配置: itunes_id: {parsed}")
        return 0

    # 搜索模式
    term = " ".join(args.term).strip()
    if not term:
        parser.print_help()
        return 1

    print(f"搜索: {term} (limit={args.limit})")
    try:
        results = search(term, args.limit, proxy)
    except Exception as e:
        print(f"[FAIL] 搜索失败: {e}")
        return 1

    if not results:
        print("没有匹配的结果")
        return 1

    print()
    for i, item in enumerate(results, 1):
        print_result(i, item)

    print("把选中节目的 itunes_id 填进 config.yaml 即可，例如：")
    print(f"  itunes_id: {results[0].get('trackId')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
