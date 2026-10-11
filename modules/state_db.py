import sqlite3
import os

class StateDB:
    def __init__(self, db_path="state.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feed_url TEXT NOT NULL,
                    guid TEXT NOT NULL,
                    title TEXT,
                    pub_date TEXT,
                    enclosure_url TEXT,
                    file_name TEXT,
                    file_size INTEGER,
                    status TEXT DEFAULT 'pending',
                    retry_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(feed_url, guid)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_feed_guid ON processed_items(feed_url, guid)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON processed_items(status)")
            conn.commit()

    def is_processed(self, feed_url, guid):
        """检查某个条目是否已处理（存在即已处理，无论成功失败）"""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT id FROM processed_items WHERE feed_url=? AND guid=?",
                (feed_url, guid)
            )
            return cur.fetchone() is not None

    def mark_processed(self, feed_url, guid, title="", pub_date="",
                       enclosure_url="", file_name="", file_size=0,
                       status="uploaded", error_message=""):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO processed_items
                    (feed_url, guid, title, pub_date, enclosure_url,
                     file_name, file_size, status, error_message, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(feed_url, guid) DO UPDATE SET
                    status=excluded.status,
                    error_message=excluded.error_message,
                    updated_at=CURRENT_TIMESTAMP
            """, (feed_url, guid, title, pub_date, enclosure_url,
                  file_name, file_size, status, error_message))
            conn.commit()

    def get_pending_items(self):
        """获取未完成（下载/上传失败）的条目，用于重试"""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT * FROM processed_items WHERE status IN ('pending', 'failed')"
            )
            return cur.fetchall()
