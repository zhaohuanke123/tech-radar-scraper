"""
main.py - 整合调度与 Markdown 报告生成模块
功能:
  1. 调用 dotnet_scraper 获取 .NET 博客文章
  2. 调用 github_scraper 获取 AI & Unity 热门仓库
  3. 将两类数据整合，渲染为排版精美的 Markdown 文件
  4. 输出至 reports/YYYY-MM-DD-Daily-Radar.md
"""

import os
import sys
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 将 src 目录加入模块搜索路径（同时支持从项目根目录和 src 目录直接运行）
_SRC_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SRC_DIR.parent
sys.path.insert(0, str(_SRC_DIR))

from dotenv import load_dotenv
from dotnet_scraper import fetch_dotnet_articles
from github_scraper import fetch_all_github_trending, TOPIC_QUERIES

# ────────────────────────────────────────────────────────────
#  初始化
# ────────────────────────────────────────────────────────────

# 优先从项目根目录的 .env 文件加载环境变量
load_dotenv(_PROJECT_ROOT / ".env")

# 配置日志：同时输出到控制台和 log 文件
log_dir = _PROJECT_ROOT / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / "scraper.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# 报告输出目录
REPORTS_DIR = _PROJECT_ROOT / "reports"


# ────────────────────────────────────────────────────────────
#  Markdown 模板渲染函数
# ────────────────────────────────────────────────────────────

def _render_dotnet_section(articles: list[dict]) -> str:
    """渲染 .NET 博客文章部分的 Markdown"""
    if not articles:
        return "## 📰 .NET 官方博客\n\n> 今日时间窗口内暂无新文章，请明日再来查看。\n"

    lines = ["## 📰 .NET 官方博客", ""]
    lines.append(f"> 数据来源：[devblogs.microsoft.com/dotnet](https://devblogs.microsoft.com/dotnet/)  ·  最近 48 小时内发布的 {len(articles)} 篇文章")
    lines.append("")

    for i, art in enumerate(articles, 1):
        lines.append(f"### {i}. [{art['title']}]({art['link']})")
        lines.append("")
        lines.append(f"- **发布时间**：{art['published']}")
        lines.append(f"- **摘要**：{art['summary']}")
        lines.append("")

    return "\n".join(lines)


def _render_github_section(category_label: str, repos: list[dict], emoji: str) -> str:
    """渲染单个 GitHub 类别的 Markdown 表格"""
    if not repos:
        return f"## {emoji} {category_label}\n\n> 暂时没有符合条件的热门仓库。\n"

    lines = [f"## {emoji} {category_label}", ""]
    lines.append(f"| # | 仓库 | ⭐ Stars | 语言 | 简介 |")
    lines.append(f"|---|------|---------|------|------|")

    for i, repo in enumerate(repos, 1):
        name = repo["name"]
        url = repo["url"]
        stars = f"{repo['stars']:,}"
        lang = repo["language"]
        # 截断描述至 60 字符，避免表格过宽
        desc = repo["description"][:60] + ("…" if len(repo["description"]) > 60 else "")
        lines.append(f"| {i} | [{name}]({url}) | {stars} | {lang} | {desc} |")

    lines.append("")
    return "\n".join(lines)


def _render_report(
    date_str: str,
    dotnet_articles: list[dict],
    github_data: dict[str, list[dict]],
) -> str:
    """
    将所有数据渲染为完整的 Markdown 报告字符串。

    Args:
        date_str: 报告日期字符串，如 "2026-02-20"
        dotnet_articles: .NET 博客文章列表
        github_data: GitHub 热门仓库数据，key 为 category_label

    Returns:
        完整的 Markdown 字符串
    """
    # 映射类别 label 到 emoji
    emoji_map: dict[str, str] = {
        TOPIC_QUERIES["ai"]["label"]: "🤖",
        TOPIC_QUERIES["unity"]["label"]: "🎮",
    }

    # ── 文件头 ──────────────────────────────────────────
    header = f"""# 🛰️ Tech Radar Daily — {date_str}

> **自动生成时间**：{datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M')} CST  
> 本报告由 [tech-radar-scraper](https://github.com) 自动生成，聚合来自 .NET 官方博客与 GitHub 的最新技术动态。

---

"""

    # ── 目录 ────────────────────────────────────────────
    toc_items = ["## 📋 目录", ""]
    toc_items.append("- [📰 .NET 官方博客](#-net-官方博客)")
    for label in github_data:
        anchor = label.lower().replace(" ", "-").replace("/", "").replace(".", "")
        toc_items.append(f"- [{emoji_map.get(label, '📦')} {label}](#{anchor})")
    toc_items.append("")
    toc_items.append("---")
    toc_items.append("")
    toc = "\n".join(toc_items)

    # ── 各章节 ──────────────────────────────────────────
    dotnet_section = _render_dotnet_section(dotnet_articles)

    github_sections = []
    for label, repos in github_data.items():
        em = emoji_map.get(label, "📦")
        github_sections.append(_render_github_section(label, repos, em))

    # ── 页脚 ────────────────────────────────────────────
    footer = """---

*由 [tech-radar-scraper](https://github.com) · Python + GitHub Actions 自动驱动*
"""

    return header + toc + dotnet_section + "\n---\n\n" + "\n---\n\n".join(github_sections) + "\n" + footer


# ────────────────────────────────────────────────────────────
#  主流程
# ────────────────────────────────────────────────────────────

def main() -> Path:
    """
    主调度函数：抓取数据 → 渲染报告 → 写入文件。

    Returns:
        生成的 Markdown 报告文件路径
    """
    # 使用北京时间（UTC+8）作为报告日期，与工作流 Cron 时间对应
    beijing_now = datetime.now(timezone(timedelta(hours=8)))
    date_str = beijing_now.strftime("%Y-%m-%d")
    report_filename = f"{date_str}-Daily-Radar.md"
    report_path = REPORTS_DIR / report_filename

    logger.info(f"{'='*60}")
    logger.info(f"  Tech Radar 每日报告生成 — {date_str}")
    logger.info(f"{'='*60}")

    # ── Step 1: 抓取 .NET 博客 ───────────────────────────
    logger.info("[1/2] 正在抓取 .NET 官方博客 RSS…")
    dotnet_articles = fetch_dotnet_articles()

    # ── Step 2: 抓取 GitHub 热门仓库 ────────────────────
    logger.info("[2/2] 正在抓取 GitHub 热门仓库…")
    github_data = fetch_all_github_trending(limit=5)
    
    # ── Step 2.5: 获取每个仓库的 README 以供分析 ─────────
    from github_scraper import fetch_repo_readme
    for label, repos in github_data.items():
        for repo in repos:
            logger.info(f"  正在获取 README: {repo['name']}")
            repo["readme"] = fetch_repo_readme(repo["name"])

    # ── Step 3: 生成总结与渲染 Markdown ──────────────────
    from llm_summarizer import generate_insight_report
    logger.info("正在调用 LLM 洞察并渲染报告…")
    llm_markdown = generate_insight_report(date_str, dotnet_articles, github_data)
    
    if llm_markdown:
        # 加上头部信息
        markdown_content = f"# 🛰️ Tech Radar Daily — {date_str}\n\n> **自动生成时间**：{beijing_now.strftime('%Y-%m-%d %H:%M')} CST  \n> 本报告由 LLM 深度分析生成。\n\n---\n\n{llm_markdown}\n\n---\n*由 [tech-radar-scraper](https://github.com) · Python + LLM 自动驱动*"
    else:
        logger.warning("LLM 分析失败或跳过，降级使用基础模板渲染。")
        markdown_content = _render_report(date_str, dotnet_articles, github_data)

    # ── Step 4: 写入文件 ─────────────────────────────────
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text(markdown_content, encoding="utf-8")

    logger.info(f"✅ 报告已生成：{report_path}")
    logger.info(f"   .NET 文章数：{len(dotnet_articles)}")
    for label, repos in github_data.items():
        logger.info(f"   {label}：{len(repos)} 个仓库")

    return report_path


if __name__ == "__main__":
    output = main()
    print(f"\n🎉 完成！报告路径：{output}")
