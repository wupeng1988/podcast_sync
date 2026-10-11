"""
代理工具：兼容 httpx 不同版本的代理参数
httpx <= 0.27 用 proxies=dict
httpx >= 0.28 用 proxy=str
"""

import httpx


def build_proxy_url(proxy_cfg):
    """从配置字典里取出一个代理 URL 字符串"""
    if not proxy_cfg:
        return None
    # 优先 https，回退 http
    return proxy_cfg.get("https") or proxy_cfg.get("http")


def create_httpx_client(proxy_cfg=None, **kwargs):
    """
    创建 httpx.Client，自动兼容新版和旧版的代理参数。
    proxy_cfg 结构：{"http": "...", "https": "..."}
    """
    if not proxy_cfg:
        return httpx.Client(**kwargs)

    proxy_url = build_proxy_url(proxy_cfg)
    if not proxy_url:
        return httpx.Client(**kwargs)

    # 优先新 API：proxy=  (httpx >= 0.26)
    try:
        return httpx.Client(proxy=proxy_url, **kwargs)
    except TypeError:
        pass

    # 回退旧 API：proxies=  (httpx <= 0.27)
    proxies = {
        "http://": proxy_cfg.get("http"),
        "https://": proxy_cfg.get("https"),
    }
    return httpx.Client(proxies=proxies, **kwargs)
