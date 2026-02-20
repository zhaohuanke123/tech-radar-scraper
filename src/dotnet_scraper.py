"""
dotnet_scraper.py - .NET 官方博客 RSS 解析模块
数据源: https://devblogs.microsoft.com/dotnet/feed/
功能: 拉取 RSS 订阅，过滤最近 48 小时内发布的文章，提取标题、链接、时间与摘要
"""

import feedparser
import logging
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

# 配置日志
logger = logging.getLogger(__name__)

# RSS 数据源地址
DOTNET_FEED_URL = "https://devblogs.microsoft.com/dotnet/feed/"

# 抓取时间窗口（小时），默认抓取最近 48 小时内的文章
HOURS_WINDOW = 48


class _MLStripper(HTMLParser):
    """简单的 HTML 标签剥离器，将摘要中的 HTML 标签清除为纯文本"""

    def __init__(self):
        super().__init__()
        self.reset()
        self.fed: list[str] = []

    def handle_data(self, d: str):
        self.fed.append(d)

    def get_data(self) -> str:
        return " ".join(self.fed)


def _strip_html(html: str) -> str:
    """去除字符串中的 HTML 标签，返回纯文本"""
    stripper = _MLStripper()
    stripper.feed(html)
    return stripper.get_data().strip()


def _truncate(text: str, max_length: int = 200) -> str:
    """将文本截断至指定长度，超出部分用省略号代替"""
    return text if len(text) <= max_length else text[:max_length].rstrip() + "…"


def fetch_dotnet_articles(hours: int = HOURS_WINDOW) -> list[dict]:
    """
    拉取并解析 .NET 博客 RSS，返回指定时间窗口内的文章列表。

    Args:
        hours: 抓取多少小时内的文章（默认 48 小时）

    Returns:
        文章列表，每个元素为包含以下字段的字典：
        - title (str): 文章标题
        - link (str): 文章 URL
        - published (str): 发布时间（ISO 8601 格式, UTC）
        - summary (str): 纯文本摘要（截断至 200 字符）
    """
    logger.info(f"正在拉取 .NET 博客 RSS: {DOTNET_FEED_URL}")

    try:
        feed = feedparser.parse(DOTNET_FEED_URL)
    except Exception as e:
        logger.error(f"RSS 拉取异常: {e}")
        return []

    if feed.bozo:
        # bozo=True 代表 RSS 格式存在问题，但不一定导致数据丢失，仅记录警告
        logger.warning(f"RSS 格式警告（bozo）: {feed.bozo_exception}")

    # 计算截止时间（当前 UTC 时间往前推 hours 小时）
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles: list[dict] = []

    for entry in feed.entries:
        # 解析发布时间
        pub_dt: datetime | None = None
        if hasattr(entry, "published"):
            try:
                pub_dt = parsedate_to_datetime(entry.published)
                # 确保有时区信息（feedparser 大多数情况下会返回带时区的时间）
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            except Exception:
                pass

        # 若无法解析时间，跳过该条目
        if pub_dt is None:
            logger.debug(f"跳过无法解析发布时间的条目: {entry.get('title', 'UNKNOWN')}")
            continue

        # 仅保留时间窗口内的文章
        if pub_dt < cutoff:
            continue

        # 提取摘要（summary 字段可能含有 HTML，需剥离）
        raw_summary = entry.get("summary", "") or ""
        clean_summary = _truncate(_strip_html(raw_summary))

        articles.append(
            {
                "title": entry.get("title", "无标题").strip(),
                "link": entry.get("link", ""),
                "published": pub_dt.strftime("%Y-%m-%d %H:%M UTC"),
                "summary": clean_summary,
            }
        )

    logger.info(f"共找到 {len(articles)} 篇最近 {hours} 小时内的 .NET 博客文章")
    return articles


# ────────────────────────────────────────────────────────────
#  本地调试入口
# ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    results = fetch_dotnet_articles()
    if results:
        for art in results:
            print(f"\n📄 {art['title']}")
            print(f"   🔗 {art['link']}")
            print(f"   🕐 {art['published']}")
            print(f"   📝 {art['summary']}")
    else:
        print("当前时间窗口内没有新文章（可尝试增大 hours 参数）")
