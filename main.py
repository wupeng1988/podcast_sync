import os
import sys
import time
import logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.config_loader import Config
from modules.logger import setup_logger
from modules.state_db import StateDB
from modules.rss_parser import fetch_feed, extract_items
from modules.itunes import lookup_feed_url
from modules.downloader import download_file
from modules.naming import get_extension, build_filename
from modules.aliyun_client import AliyunClient

logger = logging.getLogger("podcast_sync")


def resolve_rss_url(feed_cfg, config, proxy):
    """
    解析某个源的真实 RSS 地址。
    配置了 itunes_id 就先去 iTunes lookup 查（查到的 feedUrl 才是最新的地址），
    查不到或没配 itunes_id 时，回退到写死的 rss_url。
    返回 (rss_url, 错误信息)；两个来源都拿不到时 rss_url 为空。
    """
    name = feed_cfg.get("name", "")
    static_url = (feed_cfg.get("rss_url") or "").strip()
    itunes_id = feed_cfg.get("itunes_id")

    if not itunes_id:
        if not static_url:
            return "", "配置里既没有 itunes_id 也没有 rss_url"
        return static_url, ""

    resolved, err = lookup_feed_url(
        itunes_id, proxy=proxy, max_retries=config.max_retries
    )

    if resolved:
        if static_url and static_url != resolved:
            logger.info(
                f"[{name}] 配置里的 rss_url 与 iTunes 返回的不一致，改用 iTunes 的: {resolved}"
            )
        else:
            logger.info(f"[{name}] iTunes 查询到 RSS 地址: {resolved}")
        return resolved, ""

    if static_url:
        logger.warning(f"[{name}] iTunes 查询失败，回退到配置里的 rss_url | {err}")
        return static_url, ""

    return "", err


def process_feed(feed_cfg, config, state_db, aliyun):
    """处理单个 RSS 源"""
    name = feed_cfg["name"]
    aliyun_dir = feed_cfg["aliyun_dir"]
    max_items = feed_cfg.get("max_items", 10)

    # 直接拿原始代理字典：{"http": "...", "https": "..."} 或 None
    proxy = config.get_proxy_for_feed(feed_cfg)

    # 1. 解析 RSS 地址（itunes_id 优先，其次 rss_url）
    rss_url, err = resolve_rss_url(feed_cfg, config, proxy)
    if not rss_url:
        logger.error(f"[{name}] 无法获取 RSS 地址: {err}")
        return

    logger.info(f"[{name}] 开始抓取 RSS: {rss_url}")

    # 2. 抓取 RSS
    try:
        feed = fetch_feed(rss_url, proxy=proxy)
    except Exception as e:
        logger.error(f"[{name}] RSS 抓取失败: {e}")
        return

    items = extract_items(feed, max_items=max_items)
    logger.info(f"[{name}] 获取到 {len(items)} 个条目")

    # 3. 逐个处理
    new_count = 0  # 本轮实际处理的新条目
    for item in items:
        guid = item["guid"]
        if not guid:
            logger.warning(f"[{name}] 条目无 guid，跳过: {item.get('title', '')}")
            continue

        # 去重检查
        if state_db.is_processed(rss_url, guid):
            continue

        new_count += 1
        title = item["title"]
        enclosure_url = item["enclosure_url"]
        enclosure_type = item["enclosure_type"]
        pub_date = item["pub_date"]

        logger.info(f"[{name}] 新条目: {title}")

        # 4. 确定扩展名
        ext = get_extension(enclosure_url, enclosure_type)

        # 5. 下载到临时目录
        temp_name = f"{guid.replace('/', '_').replace(':', '_')[:80]}{ext}"
        temp_path = os.path.join(config.temp_dir, name, temp_name)
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)

        ok, err = download_file(
            enclosure_url, temp_path,
            proxy=proxy,
            max_retries=config.max_retries
        )

        if not ok:
            logger.error(f"[{name}] 下载失败: {title} | {err}")
            state_db.mark_processed(
                rss_url, guid, title, pub_date, enclosure_url,
                status="failed", error_message=err
            )
            continue

        file_size = os.path.getsize(temp_path)
        logger.info(f"[{name}] 下载完成: {title} ({file_size} bytes)")

        # 6. 生成最终文件名
        final_name = build_filename(name, title, temp_path, pub_date, ext)

        # 7. 上传到阿里云盘
        ok, err, file_id = aliyun.upload_file(
            temp_path, aliyun_dir, final_name, overwrite=True
        )

        if not ok:
            logger.error(f"[{name}] 上传失败: {final_name} | {err}")
            state_db.mark_processed(
                rss_url, guid, title, pub_date, enclosure_url,
                file_name=final_name, file_size=file_size,
                status="failed", error_message=err
            )
            continue

        # 8. 更新状态
        state_db.mark_processed(
            rss_url, guid, title, pub_date, enclosure_url,
            file_name=final_name, file_size=file_size,
            status="uploaded"
        )
        logger.info(f"[{name}] 上传成功: {final_name}")

        # 9. 上传间隔
        time.sleep(config.upload_delay)

    if new_count == 0:
        logger.info(f"[{name}] 没有新条目，获取到的 {len(items)} 个都已处理过，无需下载")
    logger.info(f"[{name}] 处理完成")


def cleanup_temp_files(config, state_db):
    """清理临时文件：从上传成功开始算，保留 N 天"""
    retention_days = config.temp_retention_days
    cutoff = datetime.now() - timedelta(days=retention_days)
    temp_dir = config.temp_dir

    if not os.path.exists(temp_dir):
        return

    cleaned = 0
    for root, dirs, files in os.walk(temp_dir):
        for f in files:
            fp = os.path.join(root, f)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fp))
                if mtime < cutoff:
                    os.remove(fp)
                    cleaned += 1
            except Exception as e:
                logger.warning(f"清理临时文件失败: {fp} | {e}")

    if cleaned:
        logger.info(f"清理了 {cleaned} 个临时文件（保留 {retention_days} 天）")


def run_sync():
    """执行一次完整的同步流程"""
    logger.info("=" * 50)
    logger.info("开始播客同步任务")

    try:
        config = Config("config.yaml")
        state_db = StateDB("state.db")

        # 初始化阿里云盘客户端
        aliyun_cfg = config.aliyun_cfg
        aliyun = AliyunClient(
            refresh_token=aliyun_cfg.get("refresh_token", ""),
            token_file=aliyun_cfg.get("token_file", "")
        )

        # 处理每个 RSS 源
        for feed_cfg in config.enabled_feeds():
            try:
                process_feed(feed_cfg, config, state_db, aliyun)
            except Exception as e:
                logger.error(f"[{feed_cfg['name']}] 处理异常: {e}", exc_info=True)

        # 清理临时文件
        cleanup_temp_files(config, state_db)

    except Exception as e:
        logger.error(f"同步任务异常: {e}", exc_info=True)

    logger.info("播客同步任务完成")
    logger.info("=" * 50)


def main():
    config = Config("config.yaml")
    setup_logger(
        log_level=config.global_cfg.get("log_level", "INFO"),
        log_file=config.global_cfg.get("log_file", "logs/podcast_sync.log"),
        max_bytes=config.global_cfg.get("log_max_bytes", 10485760),
        backup_count=config.global_cfg.get("log_backup_count", 5),
    )

    interval = config.schedule_interval

    if interval <= 0:
        logger.info("单次运行模式")
        run_sync()
    else:
        logger.info(f"定时运行模式，间隔 {interval} 秒（{interval/3600:.1f} 小时）")
        logger.info("立即执行首次同步...")
        run_sync()

        from apscheduler.schedulers.blocking import BlockingScheduler
        scheduler = BlockingScheduler()
        scheduler.add_job(run_sync, 'interval', seconds=interval)
        logger.info(f"定时调度已启动，下次执行将在 {interval} 秒后")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("调度已停止")


if __name__ == "__main__":
    main()
