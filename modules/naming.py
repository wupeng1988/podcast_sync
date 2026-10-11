import os
import mimetypes
from mutagen import File as MutagenFile

# 自定义 MIME 类型到扩展名的映射（补充 mimetypes 可能缺失的）
MIME_EXT_MAP = {
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/aac": ".aac",
    "audio/ogg": ".ogg",
    "audio/flac": ".flac",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "video/x-matroska": ".mkv",
}

def get_extension(enclosure_url, mime_type):
    """根据 MIME 类型或 URL 后缀获取扩展名"""
    if mime_type and mime_type in MIME_EXT_MAP:
        return MIME_EXT_MAP[mime_type]

    # 尝试从 URL 后缀获取
    from urllib.parse import urlparse
    path = urlparse(enclosure_url).path
    ext = os.path.splitext(path)[1]
    if ext:
        return ext

    # 回退：用 mimetypes 猜
    if mime_type:
        guess = mimetypes.guess_extension(mime_type)
        if guess:
            return guess

    return ".mp3"  # 最终兜底

def read_audio_metadata_title(file_path):
    """读取音频文件的元数据标题，失败返回 None"""
    try:
        audio = MutagenFile(file_path)
        if audio is None:
            return None

        # MP3 (ID3): TIT2 标签
        if hasattr(audio, 'tags') and audio.tags:
            # MP3
            if 'TIT2' in audio.tags:
                return str(audio.tags['TIT2'][0])
            # M4A / MP4: ©nam
            if '\xa9nam' in audio.tags:
                return str(audio.tags['\xa9nam'][0])
            # FLAC / OGG: title
            if 'title' in audio.tags:
                val = audio.tags['title']
                return str(val[0]) if isinstance(val, list) else str(val)
        return None
    except Exception:
        return None

def build_filename(feed_name, rss_title, file_path, pub_date, ext):
    """
    按优先级生成文件名：
    1. {RSS源名称}_{RSS标题}_{日期}.{ext}
    2. {RSS源名称}_{元数据标题}_{日期}.{ext}
    3. {RSS源名称}_{日期}.{ext}
    """
    safe_feed = sanitize(feed_name)
    date_str = format_date(pub_date)

    # 优先级 1: RSS 标题
    if rss_title and rss_title.strip():
        return f"{safe_feed}_{sanitize(rss_title)}_{date_str}{ext}"

    # 优先级 2: 音频元数据标题
    meta_title = read_audio_metadata_title(file_path)
    if meta_title and meta_title.strip():
        return f"{safe_feed}_{sanitize(meta_title)}_{date_str}{ext}"

    # 优先级 3: 兜底
    return f"{safe_feed}_{date_str}{ext}"

def sanitize(name):
    """清理文件名中的非法字符"""
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, "_")
    return name.strip().replace(" ", "_")

def format_date(pub_date):
    """将 RSS 日期转为 YYYYMMDD 格式"""
    if not pub_date:
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d")
    # feedparser 提供的 pub_date 通常是 RFC 2822 格式
    # 简单处理：提取年月日
    import re
    m = re.search(r'(\d{1,2})\s+(\w{3})\s+(\d{4})', pub_date)
    if m:
        day, mon, year = m.groups()
        month_map = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }
        mon_num = month_map.get(mon, '01')
        return f"{year}{mon_num}{int(day):02d}"
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d")
