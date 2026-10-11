import feedparser

from .proxy_manager import create_httpx_client


def fetch_feed(rss_url, proxy=None):
    """抓取并解析 RSS，返回 feedparser 对象"""
    client = create_httpx_client(
        proxy_cfg=proxy,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with client:
        resp = client.get(rss_url)
        resp.raise_for_status()
        return feedparser.parse(resp.text)


def extract_items(feed, max_items=None):
    """
    从 feed 中提取条目，返回列表。
    每个条目包含：guid, title, pub_date, enclosure_url, enclosure_type
    """
    items = []
    entries = feed.entries[:max_items] if max_items else feed.entries

    for entry in entries:
        # guid 优先，回退到 link
        guid = entry.get("id") or entry.get("link") or ""
        title = entry.get("title", "")
        pub_date = entry.get("published", "") or entry.get("updated", "")

        # 获取 enclosure（音频/视频附件）
        enclosure_url = ""
        enclosure_type = ""
        if "enclosures" in entry and entry.enclosures:
            enc = entry.enclosures[0]
            enclosure_url = enc.get("href", "")
            enclosure_type = enc.get("type", "")
        # 有些 RSS 用 media:content
        elif hasattr(entry, "media_content") and entry.media_content:
            mc = entry.media_content[0]
            enclosure_url = mc.get("url", "")
            enclosure_type = mc.get("type", "")

        if not enclosure_url:
            continue  # 跳过没有附件的条目

        items.append({
            "guid": guid,
            "title": title,
            "pub_date": pub_date,
            "enclosure_url": enclosure_url,
            "enclosure_type": enclosure_type,
        })

    return items
