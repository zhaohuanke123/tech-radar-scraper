# 🛰️ Tech Radar Scraper

> 自动化技术雷达 —— 每天早上 8 点（北京时间）为你汇总 .NET 官方博客最新动态与 GitHub 热门 AI / Unity 项目。

---

## 📁 项目结构

```
tech-radar-scraper/
├── .env.example              # 环境变量示例（复制为 .env 后填入 Token）
├── .gitignore                # Git 忽略规则
├── pyproject.toml            # uv 项目配置与依赖声明
├── README.md                 # 本文档
├── .github/
│   └── workflows/
│       └── daily_spider.yml  # GitHub Actions 工作流（每日定时触发）
├── src/
│   ├── __init__.py
│   ├── dotnet_scraper.py     # .NET 博客 RSS 解析模块
│   ├── github_scraper.py     # GitHub API 热门项目聚合模块
│   └── main.py               # 主调度 & Markdown 生成入口
├── reports/                  # 自动生成的每日 Markdown 报告（由脚本创建）
└── logs/                     # 运行日志（由脚本创建）
```

---

## 🚀 本地快速开始

### 前置要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)（推荐全局安装）

### 1. 克隆项目

```bash
git clone https://github.com/<your-username>/tech-radar-scraper.git
cd tech-radar-scraper
```

### 2. 安装 uv（若未安装）

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. 初始化虚拟环境并安装依赖

```bash
# 一条命令完成：创建 .venv 并同步依赖
uv sync
```

### 4. 配置环境变量

```bash
# 将示例文件复制为实际 .env 文件
cp .env.example .env
```

然后编辑 `.env`，填入你的 GitHub Personal Access Token：

```
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> **如何申请 Token？**  
> 访问 [github.com/settings/tokens](https://github.com/settings/tokens) → Generate new token (classic) → 勾选 `public_repo` 权限即可。

### 5. 运行爬虫

```bash
# 使用 uv run 在虚拟环境中执行（无需手动 activate）
uv run python src/main.py
```

运行成功后，报告将保存至 `reports/YYYY-MM-DD-Daily-Radar.md`。

---

## ⚙️ 配置 GitHub Secrets

若要使 GitHub Actions 工作流正常运行，需要在仓库中配置以下 Secret：

| Secret 名称 | 说明 |
|---|---|
| `GITHUB_TOKEN` | GitHub 自动提供，**无需手动创建**，工作流默认可用 |

> **注意**：工作流中同时用 `GITHUB_TOKEN` 作为 GitHub API 调用的认证凭据。  
> 内置的 `GITHUB_TOKEN` 对 **Search API** 同样有效（5000次/小时）。  
> 若需要搜索私有仓库，请额外创建一个具有 `repo` 权限的 PAT，并命名为 `GH_PAT` 后在工作流中替换。

### 配置步骤

1. 进入你的 GitHub 仓库页面
2. 点击 **Settings** → **Secrets and variables** → **Actions**
3. 点击 **New repository secret**（如需添加自定义 PAT）

---

## 📋 GitHub Actions 工作流说明

| 参数 | 值 |
|---|---|
| 触发时间 | 每天 UTC 00:00（北京时间 08:00） |
| 触发方式 | Cron 定时 + 手动触发（`workflow_dispatch`） |
| 运行环境 | `ubuntu-latest` |
| 依赖安装 | `uv sync`（缓存加速） |
| 提交策略 | 仅当 `reports/` 或 `logs/` 有变更时才提交 |

---

## 🛡️ 免责声明

本项目仅用于学习与个人技术追踪目的。数据来源于公开 RSS 订阅和 GitHub 公开 API，请遵守各平台的使用条款与速率限制规定。
