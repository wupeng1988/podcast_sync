"""
扫码获取阿里云盘 refresh_token，并自动写回 config.yaml。

用法：
    python scripts/get_token.py

行为：
    - 首次运行：弹二维码，扫码登录后从 ~/.aligo/aligo.json 读取 refresh_token
    - 自动更新项目根目录下 config.yaml 的 aliyun.refresh_token 字段
    - 保留 config.yaml 中的注释和格式
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aligo import Aligo
from ruamel.yaml import YAML

# 路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.yaml")
ALIGO_CONFIG = os.path.expanduser("~/.aligo/aligo.json")


def get_refresh_token_from_aligo():
    """从 aligo 的配置文件里读取 refresh_token"""
    if not os.path.exists(ALIGO_CONFIG):
        return None
    with open(ALIGO_CONFIG, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg.get("refresh_token") or cfg.get("refreshToken")


def update_config_yaml(refresh_token):
    """把 refresh_token 写回 config.yaml，保留注释"""
    if not os.path.exists(CONFIG_PATH):
        print(f"[ERROR] 找不到配置文件: {CONFIG_PATH}")
        return False

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.load(f)

    if "aliyun" not in cfg:
        cfg["aliyun"] = {}
    cfg["aliyun"]["refresh_token"] = refresh_token

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f)

    return True


def main():
    print("=" * 50)
    print("阿里云盘 refresh_token 获取工具")
    print("=" * 50)

    # 1. 登录（首次会弹二维码，后续直接用缓存）
    ali = Aligo()
    user = ali.get_user()
    print(f"\n登录成功！用户名: {user.user_name}")

    # 2. 读取 refresh_token
    refresh_token = get_refresh_token_from_aligo()
    if not refresh_token:
        print(f"\n[ERROR] 未能从 {ALIGO_CONFIG} 读到 refresh_token")
        return

    print(f"\nrefresh_token: {refresh_token}")

    # 3. 写回 config.yaml
    if update_config_yaml(refresh_token):
        print(f"\n[OK] 已自动写入: {CONFIG_PATH}")
        print("     字段路径: aliyun.refresh_token")
    else:
        print("\n[FAIL] 自动写入失败，请手动填写")


if __name__ == "__main__":
    main()
