"""把 aligo 轮换后的最新 refresh_token 写回 config.yaml（保留注释）。

阿里云盘的 refresh_token 是轮换制：每刷新一次 access_token，旧的
refresh_token 就作废、下发新的。正常运行时最新 token 由 aligo 自己
维护在 ~/.aligo/<name>.json，本模块只是做一层兜底——万一 token 文件
丢失，config.yaml 里的值也要尽量是「最近一次轮换后的」，否则引导
登录会直接 400 失败、触发重新扫码。
"""

import os

from ruamel.yaml import YAML


def sync_refresh_token_to_config(config_path, new_token, old_token=""):
    """new_token 与 config.yaml 中现存值不同时才写入，避免每次运行都重写文件。

    任何一步失败都不抛异常：token 回写只是兜底，不应影响同步主流程。
    返回是否实际写入了。
    """
    if not new_token or new_token == old_token:
        return False
    if not os.path.exists(config_path):
        return False

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.load(f)

        if not cfg or "aliyun" not in cfg:
            return False
        if cfg["aliyun"].get("refresh_token") == new_token:
            return False

        cfg["aliyun"]["refresh_token"] = new_token
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f)
        return True
    except Exception:
        return False
