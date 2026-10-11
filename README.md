# 播客同步工具 (podcast_sync)

从播客 RSS 源抓取新节目，下载音频到本地临时目录，再上传到 **阿里云盘**，自动去重、自动命名、支持定时运行。

单进程 Python 脚本，无框架、无数据库服务（状态存在本地 SQLite），`config.yaml` 一个文件搞定全部配置。

---

## 目录

- [功能特性](#功能特性)
- [环境要求与安装](#环境要求与安装)
- [快速开始](#快速开始)
- [扫码登录阿里云盘](#扫码登录阿里云盘)
- [配置详解](#配置详解)
- [使用方法](#使用方法)
- [运行流程](#运行流程)
- [日志与状态](#日志与状态)
- [常见问题 (FAQ)](#常见问题-faq)
- [已知限制](#已知限制)

---

## 功能特性

- **多源同步**：`config.yaml` 里可配置任意多个播客源，逐个处理。
- **两种地址来源**：填 `itunes_id`（运行时自动查最新 RSS 地址，节目换域名不用改配置），或直接写死 `rss_url`，也可两个都填互为兜底。
- **自动去重**：SQLite 记录已处理的 `guid`，重复运行不会重复下载。
- **自动命名**：`{节目名}_{标题}_{YYYYMMDD}{扩展名}`，标题优先取 RSS，其次读音频内嵌元数据，最后只留日期。
- **目录自动创建**：阿里云盘目标目录逐级查找/创建。
- **同名覆盖**：上传前删除同名文件，避免产生 `xxx(1).mp3`。
- **代理支持**：全局代理 + 单源覆盖，自动兼容 httpx 新旧版本的代理参数。
- **定时运行**：内置 APScheduler，`schedule_interval > 0` 即可常驻轮询。
- **日志**：控制台 + 滚动文件双输出。

---

## 环境要求与安装

- Python **3.8+**
- 网络：能访问播客 RSS / `itunes.apple.com` / 阿里云盘（必要时配代理）

```bash
# 1. 进入项目目录（所有路径都相对工作目录解析，务必在根目录运行）
cd podcast_sync

# 2. （建议）创建虚拟环境
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt
```

依赖说明：

| 包 | 用途 |
| --- | --- |
| `aligo` | 阿里云盘 SDK（上传、建目录） |
| `httpx` | RSS 抓取、音频下载、iTunes 查询（支持代理） |
| `feedparser` | 解析 RSS |
| `mutagen` | 读音频内嵌标题，用于兜底文件名 |
| `PyYAML` | 主程序读配置 |
| `ruamel.yaml` | `get_token.py` **写回**配置时保留注释（勿删） |
| `APScheduler` | 定时调度 |

---

## 快速开始

```bash
# ① 安装依赖
pip install -r requirements.txt

# ② 生成自己的配置（仓库里只带 config.example.yaml，config.yaml 含真实 token，不入库）
cp config.example.yaml config.yaml

# ③ 扫码登录阿里云盘，自动写入 refresh_token（详见下一节）
python scripts/get_token.py

# ④ 编辑 config.yaml：填好 feeds 列表、代理（如需要）

# ⑤ 跑一次试试
python main.py
```

首次运行会：解析 RSS → 下载未处理的新节目 → 上传到阿里云盘 → 写入 `state.db` → 清理过期临时文件。

---

## 扫码登录阿里云盘

`refresh_token` 是本工具调用阿里云盘的唯一凭证，**必须先拿到它**，否则 `AliyunClient` 会用空 token 初始化而上传失败。

### 方式一：脚本扫码（推荐）

```bash
python scripts/get_token.py
```

脚本做的事情：

1. 调用 `aligo.Aligo()` 初始化。
   - **首次运行**：终端里会打印一个 **二维码**，用阿里云盘 / 淘宝 / 支付宝 App 扫码并在手机上确认登录；
   - **已经登录过**：`~/.aligo/` 下有缓存，直接复用，不会再弹码。
2. 登录成功后打印当前用户名。
3. 从 `~/.aligo/aligo.json` 中读出 `refresh_token`。
4. **自动写回** 项目根目录 `config.yaml` 的 `aliyun.refresh_token` 字段。
   - 使用 `ruamel.yaml`，**原有注释和排版会完整保留**，不会把配置文件写成一坨。

成功输出形如：

```
==================================================
阿里云盘 refresh_token 获取工具
==================================================
登录成功！用户名: your_name

refresh_token: <你的token>
[OK] 已自动写入: /path/to/podcast_sync/config.yaml
     字段路径: aliyun.refresh_token
```

> 二维码通常几十秒到一两分钟过期，超时重新运行即可。

### 方式二：留空自动弹码

把 `config.yaml` 里的 `aliyun.refresh_token` 留空（`""`），首次运行 `python main.py` 时 `aligo` 也会尝试弹二维码登录。**但**这种方式不会把 token 写回 `config.yaml`，下次运行可能又要重新扫码，所以**不推荐**，仍建议走 `get_token.py`。

### 方式三：手动填写

如果你已经在别处拿到 token：

```yaml
aliyun:
  refresh_token: "你的token"
```

也可以用 `token_file` 指定 aligo 的**配置文件名**（对应 `Aligo(name=...)`，默认 `aligo`，即 `~/.aligo/aligo.json`）。换一个名字就是一套独立登录态，适合多账号：

```yaml
aliyun:
  refresh_token: ""
  token_file: "account2"        # → 使用 ~/.aligo/account2.json
```

> 运行途中如果 `refresh_token` 过期，aligo 默认（`re_login=True`）会**在终端里再次弹出二维码**，扫码后继续。所以常驻运行时建议让进程挂在能看到输出的终端里，或者提前留意日志。

### token 失效了怎么办？

重新执行一次即可：

```bash
python scripts/get_token.py
```

### 安全提醒

- `refresh_token` 等同于你阿里云盘账号的访问权限，**不要截图、不要发到群里、不要提交到公开仓库**。
- 项目里 `config.yaml`、`scripts/aliyun_token.txt` 都含真实 token，注意保护这两个文件。
- 怀疑泄露时，去阿里云盘 App 的「设置 → 账号安全 / 第三方应用管理」里踢掉授权，再重新扫码。

---

## 配置详解

配置文件：项目根目录 **`config.yaml`**，分四个顶层段：`global` / `aliyun` / `proxy` / `feeds`。

### `global` — 全局运行参数

```yaml
global:
  log_level: INFO              # DEBUG / INFO / WARNING / ERROR
  log_file: logs/podcast_sync.log
  log_max_bytes: 10485760      # 单个日志文件上限 10MB
  log_backup_count: 5          # 保留 5 个轮转文件

  temp_dir: ./tmp              # 音频临时下载目录（相对工作目录）
  temp_retention_days: 7       # 临时文件保留天数（按 mtime 计算，见下）

  schedule_interval: 0         # 0 = 只跑一次；86400 = 每 24 小时一轮
  download_concurrency: 5      # 预留字段，当前实现为串行，暂不生效
  upload_delay: 2              # 同一源内每次上传后 sleep 秒数（防限流）
  max_retries: 3               # 下载 / iTunes 查询的统一重试次数
```

要点：

- `temp_retention_days` 是按**文件修改时间**判断的，且**不管上传成功与否**都会被清掉（`temp_dir` 里超过 N 天的文件一律删除）。
- `upload_delay` 是刻意留的限流间隔，网络不稳或被 429 时可以调大。
- `download_concurrency` 目前读了但没用上：**所有源、所有节目都是串行处理的**。

### `aliyun` — 阿里云盘

```yaml
aliyun:
  refresh_token: "xxxx"        # 扫码登录后由 get_token.py 自动写入
  # token_file: ""             # 可选，aligo 配置文件名（Aligo(name=...)），多账号用
```

### `proxy` — 全局代理（可选）

```yaml
proxy:
  http:  "http://127.0.0.1:17439"
  https: "http://127.0.0.1:17439"
  # 带认证：
  # http: "http://username:password@127.0.0.1:7890"
```

- 不需要代理：**整段删掉或留空**即可。
- 实际生效时只会取其中**一个 URL**（优先 `https`，回退 `http`）。
- **代理只作用于**：RSS 抓取、音频下载、iTunes lookup 查询。
  **阿里云盘上传（aligo SDK）不走代理。**
- 单个源可在 feed 里覆盖（见下）。

### `feeds` — 播客源列表

每个源的字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `name` | ✅ | 节目名，同时用作临时子目录名和文件名前缀 |
| `aliyun_dir` | ✅ | 阿里云盘目标目录，如 `/Podcasts/BBC_6_Minute_English`，不存在会逐级创建 |
| `itunes_id` | 二选一 | 苹果播客节目 ID，运行时通过 iTunes lookup 查最新 RSS 地址 |
| `rss_url` | 二选一 | 直接写死的 RSS 地址，作为兜底 |
| `enabled` | ➖ | `false` 则跳过该源，默认 `true` |
| `max_items` | ➖ | 每次抓取处理的最大条目数，默认 `10` |
| `proxy` | ➖ | 覆盖全局代理，结构同顶层 `proxy` |

**校验规则**：每个 `enabled` 的源必须同时有 `name` + `aliyun_dir`，且 `itunes_id` 和 `rss_url` **至少填一个**，否则启动即抛 `ValueError`。

`itunes_id` 支持三种写法（`extract_itunes_id` 会统一解析成纯数字）：

```yaml
itunes_id: 262026947
itunes_id: "https://itunes.apple.com/lookup?id=262026947"
itunes_id: "https://podcasts.apple.com/cn/podcast/bbc-6-minute-english/id262026947"
```

**两个都填时 `itunes_id` 优先**；iTunes 查询失败则回退到 `rss_url`；两个都拿不到 → 该源本轮跳过并记 error 日志。

#### 新增一个源的完整示例

```yaml
feeds:
  - name: "某个播客"
    itunes_id: 1234567890
    rss_url: "https://example.com/feed.xml"   # 兜底，建议填
    aliyun_dir: "/Podcasts/某个播客"
    enabled: true
    max_items: 20
    # proxy:                                  # 单源专用代理
    #   http: "http://127.0.0.1:7891"
    #   https: "http://127.0.0.1:7891"
```

#### 怎么查 `itunes_id`？

仓库自带脚本：

```bash
# 按关键词搜索，列出 id + RSS
python scripts/lookup_itunes.py 6 Minute English

# 已知 id，反查它的 RSS 地址
python scripts/lookup_itunes.py --id 262026947
python scripts/lookup_itunes.py --id https://podcasts.apple.com/cn/podcast/xxx/id262026947

# 不走代理 / 指定配置文件
python scripts/lookup_itunes.py --no-proxy
python scripts/lookup_itunes.py --config /path/to/config.yaml
```

搜索输出示例：

```
1) BBC 6 Minute English
   主播:     BBC Learning English
   itunes_id: 262026947
   RSS:      https://podcasts.files.bbci.co.uk/p02pc9tn.rss
```

把 `itunes_id` 抄进 `config.yaml` 即可。

> 注意：文档里常见的示例 ID `572379590` 在 iTunes 上**查不到任何结果**（`resultCount: 0`，不是 HTTP 报错）；BBC 6 Minute English 的正确 ID 是 **262026947**。

---

## 使用方法

所有命令都在**项目根目录**执行（`config.yaml`、`state.db`、`logs/` 都按相对路径找）。

### 1. 单次运行

```bash
python main.py                 # schedule_interval: 0 时，跑完即退出
```

### 2. 常驻定时运行

```yaml
global:
  schedule_interval: 86400     # 每 24 小时同步一次
```

```bash
python main.py
# 启动后立即执行首次同步，之后每隔 interval 秒再跑一轮；
# Ctrl+C 优雅停止。
```

### 3. 后台运行

```bash
nohup python main.py >> logs/nohup.out 2>&1 &
# 查看
tail -f logs/podcast_sync.log
# 停止
pkill -f "python main.py"
```

### 4. 用 cron 跑（不想常驻进程时）

```cron
# 每天 06:30 同步一次；schedule_interval 保持 0
30 6 * * * cd /path/to/podcast_sync && /usr/bin/python3 main.py >> logs/cron.log 2>&1
```

### 5. 只跑一个模块做排查

没有测试套件，直接 import 验证：

```bash
python -c "from modules.config_loader import Config; print(Config('config.yaml').enabled_feeds())"
python scripts/lookup_itunes.py --id 262026947     # 验证 iTunes 查询链路
```

---

## 运行流程

`main.py` 是全部编排层：`run_sync()` → 遍历启用的源 → `process_feed()`。

单个源的处理步骤：

| 步骤 | 模块 | 做什么 |
| --- | --- | --- |
| 0 | `main.resolve_rss_url` | `itunes_id` → iTunes lookup 拿 `feedUrl`；失败回退 `rss_url`；都没有则跳过 |
| 1 | `rss_parser` | httpx（走代理）抓 RSS，条目按 `guid` 摊平（`entry.id` 优先，回退 `entry.link`） |
| 2 | `state_db.is_processed` | **下载前**按 `(rss_url, guid)` 去重，只认 `status='uploaded'`（`failed` 会重试） |
| 3 | `downloader` | 流式下载到 `tmp/<节目名>/<guid><ext>`，失败退避重试 1s / 4s / 16s |
| 4 | `naming.build_filename` | 生成 `{节目名}_{标题}_{YYYYMMDD}{ext}` |
| 5 | `aliyun_client` | 逐级建目录（结果缓存）→ 删同名文件 → 上传 |
| 6 | `state_db.mark_processed` | 写入 `uploaded` 或 `failed`；`file_name`/`file_size` 只在有值时回填 |

最后 `cleanup_temp_files()` 清理 `temp_dir` 中超过 `temp_retention_days` 天的文件。

代码结构：

```
podcast_sync/
├── main.py                 # 编排：run_sync / process_feed / 清理
├── config.yaml             # 配置（含 refresh_token，注意保密）
├── requirements.txt
├── state.db                # 运行时产物：去重状态（SQLite）
├── logs/                   # 运行时产物：日志
├── tmp/                    # 运行时产物：音频临时文件
├── modules/
│   ├── config_loader.py    # 配置读取 + 校验 + 便捷属性
│   ├── proxy_manager.py    # 唯一构造 httpx.Client 的地方（兼容新旧代理 API）
│   ├── rss_parser.py       # 抓取 + 解析 RSS
│   ├── itunes.py           # iTunes lookup 反查 RSS
│   ├── downloader.py       # 流式下载 + 重试
│   ├── naming.py           # 扩展名判断、文件名生成、非法字符清理
│   ├── aliyun_client.py    # 建目录 / 删同名 / 上传（aligo）
│   ├── state_db.py         # SQLite 去重表
│   └── logger.py           # 日志初始化（幂等）
└── scripts/
    ├── get_token.py        # 扫码登录并写回 refresh_token
    ├── lookup_itunes.py    # 搜节目 / 反查 RSS
    └── aliyun_token.txt    # 运行时产物，含 token
```

---

## 日志与状态

### 日志

- 文件：`logs/podcast_sync.log`（10MB 轮转，保留 5 份）
- 控制台同步输出，格式：`2026-10-11 01:23:45 [INFO] podcast_sync: ...`
- 级别由 `global.log_level` 控制，排查问题时改成 `DEBUG`。

### 状态库 `state.db`

表 `processed_items`，`UNIQUE(feed_url, guid)`：

```bash
# 看看都处理了什么
sqlite3 state.db "SELECT status, COUNT(*) FROM processed_items GROUP BY status;"

# 按节目看
sqlite3 state.db "SELECT title, file_name, status, error_message FROM processed_items ORDER BY updated_at DESC LIMIT 20;"

# 看某条失败记录的报错
sqlite3 state.db "SELECT title, error_message FROM processed_items WHERE status='failed';"
```

**重要语义**：`is_processed` 只把 `status='uploaded'` 当作已完成 —— **`failed` 的条目下一轮会自动重试**，无需手动删行。

重试就是走正常流程：该条目仍在 RSS 的 `max_items` 窗口内，轮到它时因为没被标记成 `uploaded` 而再次下载。两条边界：

- **没有重试次数上限**：源上的音频文件真挂了（404、链接永久失效），每轮都会重试一遍，日志里会一直刷这条报错。要停掉，把对应行删掉或改状态即可：
  ```bash
  sqlite3 state.db "DELETE FROM processed_items WHERE title LIKE '%节目名%';"
  ```
- **掉出窗口就不重试了**：如果失败时该条目已经排到 `max_items` 之外（默认 10），后续抓取看不到它，也就不会重试。

> 代码里还有个 `StateDB.get_pending_items()`（返回 `pending`/`failed` 行），主流程仍未调用 —— 重试不需要它，靠 `is_processed` 过滤就够。只有想重试「已掉出 RSS 窗口」的历史条目时才用得上。

---

## 常见问题 (FAQ)

**Q：运行报「RSS源必须配置 itunes_id 或 rss_url」？**
A：`config.yaml` 校验失败。给该源补上 `itunes_id`（推荐）或 `rss_url`，同时确认 `name`、`aliyun_dir` 都在。

**Q：上传失败 / 一直没传上去？**
A：先看日志里的 `error_message`：
- 含 `RATE_LIMIT:` → 阿里云盘 429 限流，调大 `upload_delay`（如 `5`）再重跑；
- token 失效 → `python scripts/get_token.py` 重新扫码；
- 其它错误 → `sqlite3 state.db "SELECT title, error_message FROM processed_items WHERE status='failed';"` 查看，**下一轮会自动重试**；若确认是坏链接、不想反复重试，删掉对应行。

**Q：节目换了域名 / RSS 地址变了，会重复下载吗？**
A：去重键是**解析后的 `rss_url`**，不是 `itunes_id`。地址一变，`state.db` 视为新源，会重新拉一遍；但上传用 `overwrite=True`，同名文件会被覆盖，**只会浪费带宽，不会产生重复文件**。想省流量就配 `itunes_id`，让地址稳定。

**Q：iTunes 查询失败，源被跳过了？**
A：单轮跳过，不会写状态，下轮还会再试。若该源没有 `rss_url` 兜底就一直失败 —— 补上 `rss_url`，或检查代理（`itunes.apple.com` 国内通常需要代理）。

**Q：想删除某个已经同步的节目让它重新下载？**
A：删 `state.db` 里对应行（见上），或者备份后直接删掉整个 `state.db`（**所有**源都会重新处理一遍）。

**Q：能加密码代理吗？**
A：可以，`http: "http://username:password@127.0.0.1:7890"`。

**Q：代理要怎么关？**
A：把 `proxy` 段整段删掉或注释掉。注意**阿里云盘上传本来就不走代理**，所以关代理只影响 RSS / 下载 / iTunes 查询。

**Q：上传也想走代理怎么办？**
A：`config.yaml` 的 `proxy` 对 aligo 无效。aligo 自己支持在 **`~/.aligo/config.json5`** 里配全局代理（同时可用 `port` 开本地 HTTP 服务做网页端扫码）：

```json5
{
  "proxies": {
    "https": "http://localhost:17439",
    "http": "http://localhost:17439"
  }
}
```

**Q：`logs/`、`tmp/`、`state.db` 要不要备份？**
A：都是运行时产物，删了会重建；但 `state.db` 删了 = 全部重新下载上传，建议保留。

---

## 已知限制

- **失败无限重试**：`failed` 记录不会被视为「已处理」，每轮都会重来，且没有次数上限；掉出 `max_items` 窗口的失败条目则再也轮不到（详见上文）。
- **串行执行**：`download_concurrency` 是预留字段，实际源与节目均串行下载，没有并发。
- **临时文件按 mtime 清理**：`temp_retention_days` 到期一律删除，不区分上传是否成功。
- **iTunes 查询不缓存**：每个源每轮多发一次 `lookup` 请求。
- **阿里云盘不走代理**：aligo SDK 不经过 `proxy_manager`。
- **429 限流**：建目录后、删除同名文件后各 `sleep(1)` 缓解，仍可能触发，报错以 `RATE_LIMIT:` 开头。
- **不是 git 仓库**：无版本控制，改动前自行备份；`config.yaml` 与 `scripts/aliyun_token.txt` 含真实凭证，切勿外传。
- **无测试 / lint 工具链**，改动后请手动跑一轮验证。
