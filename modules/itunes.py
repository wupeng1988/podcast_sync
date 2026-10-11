"""
iTunes Lookup：根据苹果播客的节目 ID 反查 RSS 地址。

接口：https://itunes.apple.com/lookup?id=572379590
返回 JSON 里的 results[*].feedUrl 就是可用的 RSS 地址。
"""

import re
import time

from .proxy_manager import create_httpx_client

LOOKUP_URL = "https://itunes.apple.com/lookup"


def extract_itunes_id(value):
    """
    从配置值里解析出节目 ID，支持三种写法：
      - 纯数字：262026947
      - lookup 链接：https://itunes.apple.com/lookup?id=572379590
      - 节目页链接：https://podcasts.apple.com/cn/podcast/xxx/id262026947
    解析不出来返回 None。
    """
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return text

    # 链接里的 ?id=xxx（或 &id=xxx）
    m = re.search(r"[?&]id=(\d+)", text)
    if m:
        return m.group(1)

    # 链接路径末尾的 /idxxx，或直接写成 idxxx
    # 前面必须是行首或 "/"，避免误伤 "valid5723" 这类字符串
    m = re.search(r"(?:^|/)id(\d+)(?:[/?#]|$)", text)
    if m:
        return m.group(1)

    return None


def lookup_feed_url(itunes_id, proxy=None, max_retries=3, timeout=30):
    """
    调用 iTunes lookup 接口查 RSS 地址。
    proxy 结构与 httpx 一致：{"http": "...", "https": "..."} 或 None。
    返回 (feed_url, 错误信息)：成功时 feed_url 非空、错误信息为空字符串。
    """
    parsed_id = extract_itunes_id(itunes_id)
    if not parsed_id:
        return "", f"无法解析 iTunes ID: {itunes_id}"

    attempts = max(1, max_retries)
    last_error = ""

    for attempt in range(attempts):
        try:
            client = create_httpx_client(
                proxy_cfg=proxy,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with client:
                resp = client.get(LOOKUP_URL, params={"id": parsed_id})
                resp.raise_for_status()
                data = resp.json()

            results = data.get("results") or []
            # 取第一条带 feedUrl 的结果
            for item in results:
                feed_url = (item.get("feedUrl") or "").strip()
                if feed_url:
                    return feed_url, ""

            if results:
                return "", f"iTunes 结果里没有 feedUrl (id={parsed_id})"
            return "", f"iTunes 未找到该节目 (id={parsed_id})"

        except Exception as e:
            last_error = str(e)
            if attempt < attempts - 1:
                time.sleep(2 ** attempt)  # 1s, 4s, 16s

    return "", last_error
