"""
github_scraper.py - GitHub API 热门项目聚合模块
功能:
  - 通过 GitHub Search API 搜索近期活跃的热门仓库
  - 支持两类主题：AI/LLM 项目 和 Unity 游戏开发工具
  - 注意：GitHub Search API 不支持 "(A OR B) AND C" 形式的括号组合查询，
    本模块改用"逐 topic 分别查询，按 stars 合并去重"的策略确保命中率
  - 妥善处理 API 速率限制（Rate Limit），超限时自动等待并重试
"""

import os
import time
import logging
import requests
from datetime import datetime, timezone, timedelta

# 配置日志
logger = logging.getLogger(__name__)

# GitHub Search API 端点
GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"

# 搜索时间范围（天）：查找最近 N 天内有活跃推送的仓库
SEARCH_DAYS = 30

# 每个主题默认返回的仓库数量上限（最终合并后再取 Top N）
DEFAULT_LIMIT = 10

# API 请求超时设置（秒）
REQUEST_TIMEOUT = 15

# ────────────────────────────────────────────────────────────
#  两类检索主题的查询配置
#  每个 topic 是独立的 GitHub topic 标签，会被单独查询后合并
# ────────────────────────────────────────────────────────────
TOPIC_QUERIES = {
    "ai": {
        "label": "AI / LLM / Agent",
        # 每个 topic 独立查询，结果按 stars 合并去重
        # 附加过滤：language:Python 确保是 AI 开发者关注的仓库
        "topics": ["llm", "agent", "generative-ai", "large-language-model"],
        "lang_filter": "language:Python",   # 可选的语言过滤
    },
    "unity": {
        "label": "Unity / 游戏开发工具",
        "topics": ["unity", "unity3d", "unity-tools", "unity-plugin"],
        "lang_filter": "",  # Unity 项目语言多样，不加语言过滤
    },
}


def _get_headers() -> dict:
    """
    构建 HTTP 请求头。
    若设置了 GITHUB_TOKEN 环境变量，则使用认证请求（速率限制从 60/h 提升至 5000/h）。
    """
    token = os.getenv("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        logger.debug("已使用 GitHub Token 认证")
    else:
        logger.warning("未设置 GITHUB_TOKEN，API 速率限制为 60次/小时（未认证）")
    return headers


def _handle_rate_limit(response: requests.Response) -> bool:
    """
    检测 API 速率限制，若已超限则阻塞等待直到重置时间，然后返回 True（调用方应重试）。
    返回 False 表示未触发速率限制，无需等待。
    """
    if response.status_code == 403:
        # GitHub 在超限时会在响应头中提供重置时间戳
        reset_ts = response.headers.get("X-RateLimit-Reset")
        if reset_ts:
            reset_time = datetime.fromtimestamp(int(reset_ts), tz=timezone.utc)
            wait_secs = max(0, (reset_time - datetime.now(timezone.utc)).total_seconds()) + 5
            logger.warning(f"GitHub API 速率限制已触发，等待 {wait_secs:.0f} 秒后重试…")
            time.sleep(wait_secs)
            return True  # 通知调用方重试
    return False


def _search_single_topic(topic: str, lang_filter: str, days: int, per_page: int = 10) -> list[dict]:
    """
    针对单个 topic 标签构造查询并发起 API 请求。

    Args:
        topic: GitHub topic 名称（不含 "topic:" 前缀），如 "llm"
        lang_filter: 语言过滤字符串，如 "language:Python"，可为空
        days: 活跃时间范围（天）
        per_page: 每次 API 请求返回的数量

    Returns:
        仓库信息字典列表
    """
    since_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    # 构建简洁直接的查询（无括号组合，GitHub API 限制）
    parts = [f"topic:{topic}", f"pushed:>{since_date}", "stars:>10"]
    if lang_filter:
        parts.append(lang_filter)
    query = " ".join(parts)

    headers = _get_headers()
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": per_page,
    }

    for attempt in range(2):  # 最多尝试 2 次（超限时等待后重试）
        logger.debug(f"  topic:{topic} 请求（第{attempt + 1}次）: {query}")
        try:
            resp = requests.get(
                GITHUB_SEARCH_URL,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as e:
            logger.error(f"网络请求失败 (topic:{topic}): {e}")
            return []

        # 检查速率限制
        if _handle_rate_limit(resp):
            continue  # 等待后重试

        if resp.status_code != 200:
            logger.warning(f"topic:{topic} 返回错误 {resp.status_code}: {resp.text[:100]}")
            return []

        items = resp.json().get("items", [])
        logger.debug(f"  topic:{topic} -> {len(items)} 条结果")
        return [
            {
                "name": item.get("full_name", ""),
                "url": item.get("html_url", ""),
                "description": (item.get("description") or "暂无描述").strip(),
                "stars": item.get("stargazers_count", 0),
                "language": item.get("language") or "N/A",
            }
            for item in items
        ]

    return []


def fetch_github_trending(
    category: str = "ai",
    limit: int = DEFAULT_LIMIT,
    days: int = SEARCH_DAYS,
) -> list[dict]:
    """
    抓取指定类别的 GitHub 热门仓库。
    策略：对该类别的每个 topic 分别查询，合并后按 stars 去重排序，取 Top N。

    Args:
        category: "ai" 或 "unity"，对应 TOPIC_QUERIES 中的配置
        limit: 最终返回数量上限
        days: 搜索多少天内活跃的仓库

    Returns:
        按 Stars 降序排列的仓库信息列表
    """
    if category not in TOPIC_QUERIES:
        raise ValueError(f"未知类别 '{category}'，可选值: {list(TOPIC_QUERIES.keys())}")

    cfg = TOPIC_QUERIES[category]
    label = cfg["label"]
    topics = cfg["topics"]
    lang_filter = cfg.get("lang_filter", "")

    logger.info(f"开始抓取 [{label}] 类别热门仓库 (近 {days} 天, 最多 {limit} 个)")
    logger.info(f"  将对 {len(topics)} 个 topic 分别查询: {topics}")

    # 用字典去重（key 为仓库 URL，保留 stars 最大的那条）
    seen: dict[str, dict] = {}
    per_topic = max(limit, 5)  # 每个 topic 多取一些，充分保证合并后有足够数量

    for topic in topics:
        results = _search_single_topic(topic, lang_filter, days, per_page=per_topic)
        for repo in results:
            url = repo["url"]
            # 如果同一仓库出现在多个 topic 中，保留 stars 最高的记录（实际上是同一个）
            if url not in seen or repo["stars"] > seen[url]["stars"]:
                seen[url] = repo
        # 友好的 API 调用间隔
        time.sleep(0.5)

    # 按 stars 降序排列，取前 limit 个
    merged = sorted(seen.values(), key=lambda r: r["stars"], reverse=True)[:limit]
    logger.info(f"[{label}] 合并去重后共 {len(merged)} 个仓库")
    return merged


def fetch_all_github_trending(limit: int = DEFAULT_LIMIT) -> dict[str, list[dict]]:
    """
    一次性抓取所有类别的 GitHub 热门仓库。

    Returns:
        字典，key 为类别 label，value 为仓库列表
    """
    result: dict[str, list[dict]] = {}
    for key, cfg in TOPIC_QUERIES.items():
        result[cfg["label"]] = fetch_github_trending(key, limit)
        time.sleep(1)  # 两个类别之间的等待
    return result


# ────────────────────────────────────────────────────────────
#  本地调试入口
# ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()  # 从 .env 文件加载 GITHUB_TOKEN

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    all_repos = fetch_all_github_trending(limit=5)
    for category_label, repos in all_repos.items():
        print(f"\n{'='*60}")
        print(f"  {category_label}")
        print(f"{'='*60}")
        for repo in repos:
            print(f"  ⭐ {repo['stars']:>6}  [{repo['language']}]  {repo['name']}")
            print(f"         {repo['url']}")
            print(f"         {repo['description'][:80]}")
