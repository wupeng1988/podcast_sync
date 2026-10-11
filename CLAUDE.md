# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Podcast sync tool: pulls podcast RSS feeds, downloads new episode audio, and uploads it to 阿里云盘 (Aliyun Drive). Single-process Python app, no package structure, no test suite, not a git repository. Comments, log messages, and config annotations are in Chinese — match that.

## Commands

```bash
python main.py              # run once (schedule_interval: 0) or loop (schedule_interval > 0)
python scripts/get_token.py # QR-login to Aliyun and write refresh_token back into config.yaml
python scripts/lookup_itunes.py 6 Minute English   # search Apple Podcasts -> itunes_id + feedUrl
python scripts/lookup_itunes.py --id 262026947     # lookup feedUrl for a known id
pip install -r requirements.txt
```

There is no build, lint, or test tooling. To exercise one piece in isolation, import it directly:

```bash
python -c "from modules.config_loader import Config; print(Config('config.yaml').enabled_feeds())"
```

Paths (`config.yaml`, `state.db`, `logs/`) are resolved relative to the working directory, so run from the repo root.

## Architecture

`main.py` is the whole orchestration layer: `run_sync()` → for each enabled feed → `process_feed()`. Everything else lives in `modules/`, one concern per file, imported flat (`from modules.x import y`).

Per-feed pipeline in `process_feed()`:

0. `main.resolve_rss_url` picks the feed URL: `itunes_id` (if present) → `itunes.lookup_feed_url` returns `results[0].feedUrl`; a failed lookup falls back to the static `rss_url`, and a feed with neither source is skipped with an error.
1. `rss_parser.fetch_feed` (httpx + proxy) → `extract_items` flattens entries to dicts keyed by `guid`, preferring `entry.id`, falling back to `entry.link`.
2. `state_db.is_processed(feed_url, guid)` dedupes **before** any work.
3. `downloader.download_file` streams to `config.temp_dir/<feed name>/<sanitized guid><ext>` with exponential backoff (1s/4s/16s).
4. `naming.build_filename` picks `{feed}_{title}_{YYYYMMDD}{ext}` — RSS title first, then embedded audio metadata via mutagen, then date only.
5. `aliyun_client.AliyunClient.upload_file` resolves/creates the folder path level-by-level (cached in `_dir_cache`), deletes a same-name file when `overwrite=True`, then uploads.
6. `state_db.mark_processed(...)` records `status` as `uploaded` or `failed`.

Cross-cutting pieces:

- **`proxy_manager.create_httpx_client`** is the only place that constructs an httpx client. It handles the old `proxies=` vs new `proxy=` API split across httpx versions and resolves the `{"http": ..., "https": ...}` dict from config to a single URL. Both `rss_parser` and `downloader` go through it; never call `httpx.Client` directly.
- **`config_loader.Config`** validates feed entries at load time (each enabled feed needs `name`, `aliyun_dir` plus at least one address source: `itunes_id` or `rss_url`) and exposes globals as properties. Proxy precedence: per-feed `proxy` overrides global `proxy`.
- **`itunes.lookup_feed_url`** calls `https://itunes.apple.com/lookup?id=<ID>` (with `proxy_manager`, same retry/backoff idea as `downloader`) and returns `(feed_url, error)`. `itunes.extract_itunes_id` accepts a bare id, a `lookup?id=` link, or a `/podcast/.../idNNN` link. When both `itunes_id` and `rss_url` are configured, `itunes_id` wins every run.
- **`state_db.StateDB`** is a SQLite table `UNIQUE(feed_url, guid)`. It opens a fresh connection per call — no shared session.
- **`logger.setup_logger`** attaches a `RotatingFileHandler` plus a console handler to the single `podcast_sync` logger; it's idempotent (returns early if handlers exist).

### Behavioral gotchas

- `state_db.is_processed` only counts rows with `status='uploaded'` as done, so `failed` rows are re-attempted on every later run (no retry cap — a permanently dead enclosure URL retries forever). Retry needs no `get_pending_items()` call: the row is still in the feed's `extract_items` window, so normal iteration picks it up; an item that has fallen out of the `max_items` window is never retried. `get_pending_items()` (returns `pending`/`failed` rows) remains unused.
- `mark_processed`'s upsert updates `status`/`error_message`/`updated_at` plus `file_name`/`file_size` — but only when the incoming values are non-empty / non-zero, so a later failed attempt doesn't wipe values an earlier attempt recorded.
- `global.download_concurrency` is read by `Config` but `process_feed` iterates sequentially — feeds and episodes are never downloaded in parallel. `upload_delay` is a `time.sleep` between uploads inside one feed.
- `cleanup_temp_files` deletes anything in `temp_dir` older than `temp_retention_days` by **mtime**, regardless of whether its upload succeeded.
- `aliyun_client` sleeps 1s after folder creation and after delete to dodge Aliyun rate limits, and surfaces 429s as an `error_message` prefixed `RATE_LIMIT:`.
- Aliyun SDK calls go through the `aligo` library, which does **not** use `proxy_manager` — proxy config affects RSS fetching, episode downloads, and the iTunes lookup, nothing else.
- Dedup key is the **resolved** `rss_url`, not `itunes_id`. If Apple returns a different `feedUrl` than an earlier run (host migration), `state_db` sees a new feed and re-downloads its items — uploads use `overwrite=True`, so this costs bandwidth rather than duplicate files.
- The iTunes lookup happens once per feed per run (an extra HTTP request); no caching across runs. If it fails and the feed has no `rss_url` fallback, the feed is skipped for that run only.
- `572379590` (a common example id in the iTunes docs) resolves to **no** results; BBC 6 Minute English is `262026947`. An unknown/removed id yields `resultCount: 0` rather than an HTTP error.

## Repository artifacts

`state.db`, `logs/`, `tmp/` (downloaded audio) are runtime output, not source. `config.yaml` holds a live `aliyun.refresh_token`; `scripts/aliyun_token.txt` also carries a token. `scripts/get_token.py` rewrites `config.yaml` with `ruamel.yaml` specifically to preserve its comments — keep that dependency.
