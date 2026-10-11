import os
import time

from .proxy_manager import create_httpx_client


def download_file(url, save_path, proxy=None, max_retries=3, timeout=300):
    """
    下载文件到本地，支持重试。
    proxy 是 httpx.Client 需要的格式（dict 或 str），
    这里统一通过 create_httpx_client 处理。
    返回 (成功?, 错误信息)
    """
    last_error = ""
    for attempt in range(max_retries):
        try:
            client = create_httpx_client(
                proxy_cfg=proxy,
                timeout=timeout,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with client:
                with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    with open(save_path, "wb") as f:
                        for chunk in resp.iter_bytes(chunk_size=65536):
                            f.write(chunk)

            # 验证文件非空
            if os.path.getsize(save_path) == 0:
                raise Exception("下载文件为空")

            return True, ""

        except Exception as e:
            last_error = str(e)
            if attempt < max_retries - 1:
                wait = 2 ** (2 * attempt)  # 1s, 4s, 16s
                time.sleep(wait)

    return False, last_error
