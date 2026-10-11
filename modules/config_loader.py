import yaml
import os

class Config:
    def __init__(self, path="config.yaml"):
        with open(path, "r", encoding="utf-8") as f:
            self.raw = yaml.safe_load(f)

        self.global_cfg = self.raw.get("global", {})
        self.aliyun_cfg = self.raw.get("aliyun", {})
        self.proxy_cfg = self.raw.get("proxy", {})
        self.feeds = self.raw.get("feeds", [])

        self._validate()

    def _validate(self):
        for f in self.feeds:
            if f.get("enabled", True):
                # 名称和阿里云目录是硬要求
                for k in ["name", "aliyun_dir"]:
                    if k not in f:
                        raise ValueError(f"RSS源配置缺少字段 {k}: {f}")
                # RSS 地址来源二选一：
                #   itunes_id - 运行时通过 iTunes lookup 查真实 RSS 地址
                #   rss_url   - 直接写死
                if not f.get("itunes_id") and not f.get("rss_url"):
                    raise ValueError(
                        f"RSS源必须配置 itunes_id 或 rss_url 其中之一: {f}"
                    )

    # 便捷访问
    @property
    def temp_dir(self):
        p = self.global_cfg.get("temp_dir", "./tmp")
        os.makedirs(p, exist_ok=True)
        return p

    @property
    def temp_retention_days(self):
        return self.global_cfg.get("temp_retention_days", 7)

    @property
    def schedule_interval(self):
        return self.global_cfg.get("schedule_interval", 86400)

    @property
    def download_concurrency(self):
        return self.global_cfg.get("download_concurrency", 5)

    @property
    def upload_delay(self):
        return self.global_cfg.get("upload_delay", 2)

    @property
    def max_retries(self):
        return self.global_cfg.get("max_retries", 3)

    def get_proxy_for_feed(self, feed):
        """获取某个RSS源对应的代理配置，优先使用源级别配置"""
        if "proxy" in feed and feed["proxy"]:
            return feed["proxy"]
        return self.proxy_cfg

    def enabled_feeds(self):
        return [f for f in self.feeds if f.get("enabled", True)]
