"""
================================================================================
  Hermes Skill Market API Server — 技能市场 HTTP API 服务
================================================================================

独立的顶层 HTTP 应用，基于 aiohttp 框架，不依赖 Hermes 运行时环境。
供前端页面或脚本调用，对接后端技能市场 ClientController 接口。

启动方式:
    python skill_market_api.py [port]
    默认端口: 8643
    默认地址: http://127.0.0.1:8643

路由前缀: /api/skill-market/

提供的接口:
    1. GET  /api/skill-market/list                       查询市场技能
    2. GET  /api/skill-market/local                      查询本地已安装技能
    3. GET  /api/skill-market/skills/{id}/versions/{ver}/download  代理下载技能 ZIP
    4. POST /api/skill-market/install                    安装技能 (下载 ZIP → 解压到本地)
    5. POST /api/skill-market/uninstall                  卸载技能 (删除本地目录)
    6. GET  /health                                      健康检查

配置文件:
    后端连接配置从项目目录下的 hub_config.yaml 读取（skillhub 段），
    也可以正常加载同目录的 hub_config.yaml 文件。
    如果配置文件不存在，则使用默认的 localhost mock 模式。

依赖:
    pip install aiohttp pyyaml

独立运行说明:
    本文件已将所有 Hermes 内部依赖（如 hermes_constants）内联处置，
    可直接 `python skill_market_api.py` 启动，无需 Hermes 运行时。
================================================================================
"""

import io
import json
import logging
import os
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import quote

# ── 可选依赖：yaml（仅用于读取 hub_config.yaml） ──────────────────────────
#  如果 pyyaml 未安装，退化为空配置（使用 localhost mock 模式）
try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False
    yaml = None  # 避免后续 NameError


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                        日志 & 配置初始化                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("skill-market-api")


# ── Hermes 主目录 ─────────────────────────────────────────────────────────
#   原代码依赖 from hermes_constants import get_hermes_home
#   这里内联实现：默认指向 ~/.hermes，可通过环境变量 HERMES_HOME 覆盖
def get_hermes_home() -> Path:
    """
    获取 Hermes 主目录路径。

    优先级（带 skills 目录存在性校验）:
        1. 环境变量 HERMES_HOME（但会校验其下 skills 目录是否存在，
           若不存在则自动降级到后续候选路径）
        2. 环境变量 HOME / USERPROFILE 下的 .hermes 目录
        3. 当前用户目录下的 .hermes 目录
        4. 系统级兜底路径:
           - Windows: C:\.hermes（使用 SystemDrive 环境变量灵活适配）
           - Linux/macOS: ~/.hermes

    所有候选路径去重后，依次校验其 skills 子目录是否存在，
    返回第一个 skills 目录存在的路径。
    若全部不存在，回退到优先级最高的候选（兼容原行为）。

    返回:
        Path 对象，指向 Hermes 主目录。
    """
    candidates = []

    # 优先级 1: 环境变量 HERMES_HOME
    env_home = os.environ.get("HERMES_HOME")
    if env_home:
        candidates.append(Path(env_home))

    # 优先级 2 & 3: 用户主目录下的 .hermes
    user_home = os.environ.get("HOME") or os.environ.get("USERPROFILE") or str(Path.home())
    candidates.append(Path(user_home) / ".hermes")

    # 优先级 4: 系统级兜底路径（兼容 Windows / Linux / macOS）
    if sys.platform == "win32":
        system_drive = os.environ.get("SystemDrive", "C:")
        candidates.append(Path(f"{system_drive}\\") / ".hermes")
    else:
        candidates.append(Path.home() / ".hermes")

    # 去重保留顺序
    seen = set()
    unique_candidates = []
    for p in candidates:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            unique_candidates.append(p)

    # 逐个校验，返回第一个 skills 目录存在的路径
    for candidate in unique_candidates:
        skills_dir = candidate / "skills"
        if skills_dir.is_dir():
            return candidate

    # 全部校验失败，回退到优先级最高的候选（兼容原行为）
    return unique_candidates[0]


HERMES_HOME = get_hermes_home()
SKILLS_DIR = HERMES_HOME / "skills"  # 本地技能存放目录：~/.hermes/skills/

# 后端配置文件路径（与本文件同目录）
HUB_CONFIG_PATH = Path(__file__).parent / "hub_config.yaml"


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                     配置加载 & 认证工具函数                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def _load_hub_config() -> dict:
    """
    从 hub_config.yaml 加载后端连接配置。

    如果 pyyaml 未安装或配置文件不存在，返回空字典，后续将使用默认值。

    返回:
        dict: 配置字典，格式为 {"skillhub": {"base_url": "...", "username": "...", "password": "..."}}
    """
    if not _HAS_YAML:
        logger.warning("pyyaml 未安装，无法读取 hub_config.yaml，将使用默认 mock 模式")
        return {}

    try:
        if HUB_CONFIG_PATH.exists():
            with open(HUB_CONFIG_PATH, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        else:
            logger.info(
                "hub_config.yaml 不存在（路径: %s），将使用默认 mock 模式。"
                "可创建该文件来配置后端连接：\n"
                "  skillhub:\n"
                "    base_url: \"http://your-server:8080/api/v1\"\n"
                "    username: \"admin\"\n"
                "    password: \"your-password\"",
                HUB_CONFIG_PATH,
            )
    except Exception as e:
        logger.warning("读取 hub_config.yaml 失败: %s，将使用默认 mock 模式", e)

    return {}


def _load_skillhub_config() -> dict:
    """
    加载后端技能市场连接配置（带默认值）。

    配置来源: hub_config.yaml 中的 skillhub 段。

    返回:
        dict: {
            "base_url": 后端 API 基地址，默认 "http://localhost:8080/api/v1"
            "username": 登录用户名，默认 "local-admin"
            "password": 登录密码，默认 ""（空密码 → mock 模式）
        }
    """
    cfg = _load_hub_config().get("skillhub", {})
    return {
        "base_url": cfg.get("base_url", "http://localhost:8080/api/v1"),
        "username": cfg.get("username", "local-admin"),
        "password": cfg.get("password", ""),
    }


# 启动时加载的后端基地址（模块级常量）
SKILLHUB_URL = _load_skillhub_config()["base_url"]


def _fetch_json(url: str, timeout: int = 20) -> list | dict | None:
    """
    通用 HTTP GET → JSON 解析工具函数。

    参数:
        url:     请求地址
        timeout: 超时秒数，默认 20

    返回:
        解析后的 JSON 对象（list 或 dict），失败返回 None
    """
    try:
        with urlopen(url, timeout=timeout) as resp:
            if resp.status != 200:
                logger.warning("HTTP %s for %s", resp.status, url)
                return None
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.warning("fetch_json 失败: %s - %s", url, e)
        return None


def _build_auth_headers() -> dict:
    """
    构建调用后端 API 所需的认证请求头。

    认证流程（两种模式）:
        A. 有密码模式:
           1. POST {base_url}/auth/local/login 发送 JSON 登录请求
           2. 优先从 Set-Cookie 响应头提取 Cookie
           3. 其次从响应 JSON 中提取 token/accessToken，组 Bearer 头
        B. Mock 模式（密码为空）:
           发送 X-Mock-User-Id 头，直接使用用户名作为用户标识

    返回:
        dict: 可直接传入 urllib Request 的 headers 字典
    """
    auth = _load_skillhub_config()
    username = auth["username"]
    password = auth["password"]

    # ── 无密码 → Mock 模式 ──
    if not password:
        logger.debug("使用 Mock 认证模式 (X-Mock-User-Id: %s)", username)
        return {"X-Mock-User-Id": username}

    # ── 有密码 → 标准登录流程 ──
    try:
        login_data = json.dumps({"username": username, "password": password}).encode()
        req = Request(
            f"{SKILLHUB_URL}/auth/local/login",
            data=login_data,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))

            # 策略 1: 提取 Set-Cookie（适用于 Session 认证）
            #   hasattr 检查兼容不同 Python 版本的 http.client.HTTPResponse
            all_cookies = resp.headers.get_all("Set-Cookie") if hasattr(resp.headers, "get_all") else []
            if not all_cookies:
                raw_cookie = resp.headers.get("Set-Cookie", "")
                all_cookies = [raw_cookie] if raw_cookie else []

            cookies = []
            for raw in all_cookies:
                # Cookie 格式: "key=value; Path=/; HttpOnly; ..."
                # 只取第一个分号前的键值对
                semi = raw.find(";")
                part = raw[:semi] if semi != -1 else raw
                part = part.strip()
                if part and "=" in part:
                    cookies.append(part)

            if cookies:
                cookie_header = "; ".join(cookies)
                logger.debug("使用 Cookie 认证")
                return {"Cookie": cookie_header}

            # 策略 2: 提取 JWT token（适用于 Bearer Token 认证）
            token = body.get("token") or body.get("accessToken") or ""
            if token:
                logger.debug("使用 Bearer Token 认证")
                return {"Authorization": f"Bearer {token}"}

    except Exception as e:
        logger.warning("SkillHub 登录失败，回退到 mock 认证: %s", e)

    # 所有认证方式都失败 → 回退到 mock 模式
    return {"X-Mock-User-Id": username}


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                        业务逻辑：查询 & 扫描                                  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def fetch_market_skills() -> list:
    """
    调用后端 ``GET /client/skills/list`` 获取市场全部技能。

    这是查询后端技能市场的核心函数，所有市场技能列表接口都由此获取原始数据。

    返回:
        list[dict]: 技能对象列表，每个 dict 包含 id/name/slug/description/… 等字段。
                    如果后端不可达或返回异常，返回空列表（不抛异常）。
    """
    url = f"{SKILLHUB_URL}/client/skills/list"
    headers = _build_auth_headers()
    headers["Accept"] = "application/json"

    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=30) as resp:
            if resp.status != 200:
                logger.warning("后端返回 HTTP %s for /client/skills/list", resp.status)
                return []
            body = json.loads(resp.read().decode("utf-8"))

            # 后端标准响应格式: {"code": "0000", "data": [...]}
            if body.get("code") == "0000" and isinstance(body.get("data"), list):
                return body["data"]

            logger.warning("后端返回异常格式: %s", json.dumps(body, ensure_ascii=False)[:200])
            return []
    except Exception as e:
        logger.warning("fetch_market_skills 失败: %s", e)
        return []


def _scan_skills_recursive(parent_dir: Path, category: str) -> list:
    """
    递归扫描技能目录。

    支持两种目录结构：
        1. 扁平结构: skills/<skill_dir>/SKILL.md            （namespaceName = "default"）
        2. 分类结构: skills/<category>/<skill_dir>/SKILL.md  （namespaceName = category）

    自动判断：
        - 若当前目录直接包含 SKILL.md 子目录 → 扫描其子目录作为技能
        - 否则 → 把自身当分类，递归扫描子目录

    返回:
        list[dict]: 技能对象列表
    """
    results = []

    # 检查当前目录是否包含 SKILL.md（扁平结构的技能目录直接走了这条）
    # 但这里 parent_dir 是 skills/ 本身，它不会有 SKILL.md；此分支实际对分类层不生效

    # 遍历当前目录下的子目录
    for entry in sorted(parent_dir.iterdir()):
        if not entry.is_dir():
            continue

        # 如果这个子目录下直接有 SKILL.md，则它是一个技能目录
        if (entry / "SKILL.md").exists():
            skill_dir = entry
            # ── 解析 SKILL.md 的 YAML frontmatter ──
            name = skill_dir.name
            description = ""
            visibility = "personal"

            try:
                content = (skill_dir / "SKILL.md").read_text("utf-8")[:4000]
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = parts[1]
                        for line in frontmatter.split("\n"):
                            line = line.strip()
                            if line.startswith("name:"):
                                name = line.split(":", 1)[1].strip().strip('"').strip("'")
                            elif line.startswith("description:"):
                                description = line.split(":", 1)[1].strip().strip('"').strip("'")
                            elif line.startswith("visibility:"):
                                visibility = line.split(":", 1)[1].strip().strip('"').strip("'")
            except Exception:
                pass

            # 用技能目录的创建时间作为安装时间
            try:
                ctime = datetime.fromtimestamp(
                    skill_dir.stat().st_ctime
                ).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                ctime = ""

            results.append({
                "id": f"local-{category}-{skill_dir.name}",
                "name": name,
                "slug": skill_dir.name,
                "namespaceId": "local",
                "namespaceName": category,
                "description": description,
                "visibility": visibility,
                "status": "active",
                "currentVersion": "",
                "downloadCount": 0,
                "starCount": 0,
                "ratingAvg": 0.0,
                "ratingCount": 0,
                "latestVersion": "",
                "lastVersionId": "",
                "tags": [],
                "createTime": ctime,
                "updateTime": "",
                "createNo": "local",
                "_source": "local",
            })
        else:
            # 子目录下没有 SKILL.md → 它是个分类目录 / 进一步嵌套
            # 递归进入，把这个子目录的 name 作为新的 category
            # 但需判断：若是形如 creative/ 的分类层，第一层 entry.name 是 "creative"
            # 此时 entry 下面还有子目录（如 architecture-diagram/）才有 SKILL.md
            # 所以递归进去，category = entry.name
            results.extend(_scan_skills_recursive(entry, entry.name))

    return results


def scan_local_skills() -> list:
    """
    扫描 ``~/.hermes/skills/`` 目录，返回本地已安装的技能列表。

    支持两种目录结构（兼容）：

        扁平结构::

            ~/.hermes/skills/
            ├── dianfei-cuishou/     ← 技能目录（含 SKILL.md）
            │   └── SKILL.md
            └── precise-math/
                └── SKILL.md

        分类结构::

            ~/.hermes/skills/
            ├── creative/            ← 分类目录（namespaceName）
            │   ├── ascii-art/       ← 技能目录（含 SKILL.md）
            │   │   └── SKILL.md
            │   └── p5js/
            │       └── SKILL.md
            └── mcp/
                └── native-mcp/
                    └── SKILL.md

    每个 SKILL.md 的前置元数据（YAML frontmatter）示例::

        ---
        name: "PDF 处理工具"
        description: "处理 PDF 文件的技能"
        visibility: personal
        ---
        # 技能正文 ...

    返回:
        list[dict]: 本地技能对象列表，包含 _source: "local" 标记以区分来源。
                    如果 skills 目录不存在则为空列表。
    """
    if not SKILLS_DIR.exists():
        logger.debug("本地 skills 目录不存在: %s", SKILLS_DIR)
        return []

    results = []
    try:
        # 遍历 skills/ 一级目录
        for entry in sorted(SKILLS_DIR.iterdir()):
            if not entry.is_dir():
                continue

            # 场景 A: 扁平结构 — entry 自己就是技能目录（含 SKILL.md）
            # 场景 B: 分类结构 — entry 是分类目录，其子目录才是技能目录
            if (entry / "SKILL.md").exists():
                # ── 场景 A：扁平结构，entry 本身就是技能目录 ──
                skill_dir = entry
                category = "default"
                # ── 解析 SKILL.md 的 YAML frontmatter ──
                name = skill_dir.name
                description = ""
                visibility = "personal"

                try:
                    content = (skill_dir / "SKILL.md").read_text("utf-8")[:4000]
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            frontmatter = parts[1]
                            for line in frontmatter.split("\n"):
                                line = line.strip()
                                if line.startswith("name:"):
                                    name = line.split(":", 1)[1].strip().strip('"').strip("'")
                                elif line.startswith("description:"):
                                    description = line.split(":", 1)[1].strip().strip('"').strip("'")
                                elif line.startswith("visibility:"):
                                    visibility = line.split(":", 1)[1].strip().strip('"').strip("'")
                except Exception:
                    pass

                # 用技能目录的创建时间作为安装时间
                try:
                    ctime = datetime.fromtimestamp(
                        skill_dir.stat().st_ctime
                    ).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    ctime = ""

                results.append({
                    "id": f"local-default-{skill_dir.name}",
                    "name": name,
                    "slug": skill_dir.name,
                    "namespaceId": "local",
                    "namespaceName": "default",
                    "description": description,
                    "visibility": visibility,
                    "status": "active",
                    "currentVersion": "",
                    "downloadCount": 0,
                    "starCount": 0,
                    "ratingAvg": 0.0,
                    "ratingCount": 0,
                    "latestVersion": "",
                    "lastVersionId": "",
                    "tags": [],
                    "createTime": ctime,
                    "updateTime": "",
                    "createNo": "local",
                    "_source": "local",
                })
            else:
                # ── 场景 B：分类结构（或混合嵌套），递归扫描 ──
                # entry 自身不含 SKILL.md，其子目录中才含
                results.extend(_scan_skills_recursive(entry, entry.name))

    except Exception as e:
        logger.error("scan_local_skills 异常: %s", e)

    return results


def build_response(skills: list, total: int = 0) -> dict:
    """
    构建统一的 JSON 响应结构，对齐后端 ClientController 接口文档格式。

    参数:
        skills: 技能对象列表
        total:  总数（为 0 时自动使用 len(skills)）

    返回:
        dict: {"code": "0000", "message": "成功", "data": [...], "total": N}
    """
    return {
        "code": "0000",
        "message": "成功",
        "data": skills,
        "total": total or len(skills),
    }


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                      业务逻辑：安装 & 卸载                                    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def _fetch_bytes(url: str, timeout: int = 60, headers: dict = None) -> bytes | None:
    """
    HTTP GET → 原始字节流。

    参数:
        url:     请求地址
        timeout: 超时秒数（ZIP 下载可能较大，默认 60s）
        headers: 额外的请求头

    返回:
        bytes | None: 响应体字节流，失败返回 None
    """
    try:
        req = Request(url, headers=headers or {})
        with urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                logger.warning("_fetch_bytes 失败: HTTP %s %s", resp.status, url)
                return None
            return resp.read()
    except Exception as e:
        logger.warning("_fetch_bytes 失败: %s - %s", url, e)
        return None


def install_skill(skill_id: str, version_id: str = None, version: str = None) -> dict:
    """
    从后端市场下载技能 ZIP 并安装到 ``~/.hermes/skills/<namespace>/<slug>/``。

    完整流程:
        1. 从市场数据中查找技能详情 → 获取 slug、namespaceName、lastVersionId
        2. 确定要下载的 versionId（优先参数传入，其次 lastVersionId）
        3. 检查本地是否已安装（按 slug 去重）
        4. 调用后端下载接口: GET /client/skills/{id}/versions/{ver}/download
        5. 在内存中解析 ZIP
        6. 将 ZIP 内容写入 ~/.hermes/skills/<namespace>/<slug>/

    安全措施:
        - 拒绝 > 500KB 的单个文件
        - 拒绝包含 ".." 的路径（防路径穿越）
        - 跳过文件夹条目

    参数:
        skill_id:   技能 ID（市场列表中 id 字段）
        version_id: 版本 ID（可选，不传则使用 lastVersionId）
        version:    语义化版本号（可选，仅用于日志显示）

    返回:
        dict: {"ok": True/False, "message": "..."}
    """
    # ── 步骤 1: 从市场数据中查找技能详情 ──
    market_skills = fetch_market_skills()
    skill = next((s for s in market_skills if s.get("id") == skill_id), None)
    if skill is None:
        return {"ok": False, "message": f"技能 ID '{skill_id}' 在市场中未找到"}

    slug = skill.get("slug", skill_id)
    display_name = skill.get("name", slug)
    namespace_name = skill.get("namespaceName", "self-hosted")
    last_version_id = skill.get("lastVersionId", "")

    # ── 步骤 2: 确定要下载的版本 ID ──
    #   优先级: 参数传入 > 市场 lastVersionId > latestVersion > currentVersion > "1.0.0"
    ver_id = version_id or last_version_id
    if not ver_id:
        ver_id = version or skill.get("latestVersion") or skill.get("currentVersion") or "1.0.0"

    # ── 步骤 3: 检查是否已安装（按 slug 去重） ──
    local_skills = scan_local_skills()
    if any(s["slug"] == slug for s in local_skills):
        return {"ok": False, "message": f"技能 '{display_name}' 已安装"}

    # ── 步骤 4: 下载 ZIP ──
    download_url = (
        f"{SKILLHUB_URL}/client/skills/{quote(skill_id)}/versions/{quote(ver_id)}/download"
    )
    headers = _build_auth_headers()
    raw = _fetch_bytes(download_url, headers=headers)
    if raw is None:
        return {"ok": False, "message": f"下载技能 '{slug}' 失败 (versionId={ver_id})"}

    # ── 步骤 5: 在内存中解析 ZIP ──
    files: dict[str, str] = {}  # key: 相对路径, value: 文件内容（字符串）
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for info in zf.infolist():
                # 跳过文件夹条目
                if info.is_dir():
                    continue
                # 安全限制: 跳过超大文件
                if info.file_size > 500_000:
                    logger.warning("跳过超大文件: %s (%d bytes)", info.filename, info.file_size)
                    continue
                try:
                    files[info.filename] = zf.read(info.filename).decode("utf-8")
                except (UnicodeDecodeError, KeyError):
                    # 二进制文件或损坏的条目 → 跳过
                    continue
    except zipfile.BadZipFile:
        return {"ok": False, "message": "下载的文件不是有效的 ZIP"}

    if not files:
        return {"ok": False, "message": "ZIP 中没有有效文件"}

    # ── 步骤 6: 写入本地 ~/.hermes/skills/<namespace>/<slug>/ ──
    target_dir = SKILLS_DIR / namespace_name / slug
    target_dir.mkdir(parents=True, exist_ok=True)

    for rel_path, content in files.items():
        # 安全: 防路径穿越攻击
        clean_path = Path(rel_path)
        if ".." in clean_path.parts:
            logger.warning("拒绝可疑路径: %s", rel_path)
            continue

        file_path = target_dir / clean_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    ver_display = version or skill.get("latestVersion") or skill.get("currentVersion") or ""
    logger.info("技能安装成功: '%s' (v%s) → %s", slug, ver_display, target_dir)
    return {"ok": True, "message": f"技能 '{display_name}' 安装成功 (v{ver_display})"}


def uninstall_skill(slug: str) -> dict:
    """
    从 ``~/.hermes/skills/`` 卸载指定技能。

    在所有分类目录下搜索匹配 slug 的技能目录并删除。
    同时支持两种目录结构:
        - 扁平结构: skills/<slug>/           (技能目录直接挂在 skills/ 根级)
        - 分类结构: skills/<category>/<slug>/ (技能目录在分类子目录下)

    参数:
        slug: 技能 slug（目录名）

    返回:
        dict: {"ok": True/False, "message": "..."}
              如果删除了至少一个目录 → ok=True
              如果未找到任何匹配目录 → ok=False, 404
    """
    if not SKILLS_DIR.exists():
        return {"ok": False, "message": f"技能 '{slug}' 未安装"}

    removed = False

    for entry in sorted(SKILLS_DIR.iterdir()):
        if not entry.is_dir():
            continue

        if (entry / "SKILL.md").exists():
            # ── 场景 A: 扁平结构 — entry 自己是技能目录 ──
            if entry.name == slug:
                shutil.rmtree(entry)
                logger.info("卸载技能(扁平): '%s' (自 skills/ 根级)", slug)
                removed = True
        else:
            # ── 场景 B: 分类结构 — entry 是分类目录 ──
            skill_dir = entry / slug
            if skill_dir.exists() and skill_dir.is_dir():
                shutil.rmtree(skill_dir)
                logger.info("卸载技能(分类): '%s' (来自 %s)", slug, entry.name)
                removed = True

    if removed:
        return {"ok": True, "message": f"技能 '{slug}' 卸载成功"}
    else:
        return {"ok": False, "message": f"技能 '{slug}' 未安装"}


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    业务逻辑：导入个人技能（本地创建/导入）                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def import_local_skill(
    name: str,
    display_name: str = "",
    description: str = "",
    category: str = "",
    visibility: str = "personal",
    version: str = "",
    author: str = "",
    tags: list | None = None,
    content: str = "",
    files: dict | None = None,
) -> dict:
    """
    将外部技能创建/导入到本地 Hermes 的 skills/ 目录下，作为个人私人技能。

    完整流程:
        1. 校验 slug 格式合法性（小写字母、数字、连字符，最长 64 字符）
        2. 校验 content 必填
        3. 检查本地 skills 目录是否已存在同名技能（支持扁平 + 分类结构）
        4. 构造目标路径: skills/[category/]{name}/
        5. 组装 SKILL.md（YAML frontmatter + content）
        6. 写入 SKILL.md
        7. 遍历写入 files 字典中的附加文件
        8. 返回结果

    参数:
        name:        技能目录名（slug），小写字母/数字/连字符，最长 64 字符。必填。
        display_name: 显示名称（SKILL.md name 字段）。可选，不传则用 name。
        description: 技能描述。可选。
        category:    分类目录名。可选，不传/空字符串则放到 skills/ 根级。
        visibility:  可见性，默认 "personal"。可选值: personal, private, public。
        version:     版本号。可选。
        author:      作者。可选。
        tags:        标签列表。可选。
        content:     SKILL.md 正文内容（Markdown，不含 frontmatter）。必填。
        files:       附加文件字典，key=相对路径，value=文件内容。可选。

    返回:
        dict: {"ok": True/False, "message": "...", "path": "..."}
    """
    import re

    # ── 步骤 1: 校验 slug ──
    if not name or not name.strip():
        return {"ok": False, "message": "技能名称（name）不能为空"}

    slug = name.strip().lower()
    if not re.match(r'^[a-z0-9][a-z0-9\-]{0,62}[a-z0-9]$', slug) and not re.match(r'^[a-z0-9]$', slug):
        return {
            "ok": False,
            "message": (
                "技能名称（name）格式不正确。规则：只能包含小写字母、数字和连字符；"
                "必须以字母或数字开头和结尾；长度 1-64 字符"
            ),
        }
    if len(slug) > 64:
        return {"ok": False, "message": "技能名称（name）长度不能超过 64 字符"}

    # ── 步骤 2: 校验 content ──
    if not content or not content.strip():
        return {"ok": False, "message": "技能内容（content）不能为空"}

    # ── 步骤 3: 检查是否已存在（同名 slug 去重） ──
    local_skills = scan_local_skills()
    if any(s["slug"] == slug for s in local_skills):
        return {"ok": False, "message": f"技能 '{slug}' 已存在，请使用其他名称"}

    # ── 步骤 4: 构造目标路径 ──
    cat = category.strip() if category and category.strip() else ""
    if cat:
        target_dir = SKILLS_DIR / cat / slug
    else:
        target_dir = SKILLS_DIR / slug

    # ── 步骤 5: 组装 SKILL.md ──
    fm_lines = []
    fm_lines.append(f"name: \"{display_name or slug}\"")
    if description:
        fm_lines.append(f"description: \"{description}\"")
    fm_lines.append(f"visibility: {visibility}")
    if version:
        fm_lines.append(f"version: \"{version}\"")
    if author:
        fm_lines.append(f"author: \"{author}\"")
    if tags:
        # 支持 tags 数组或逗号分隔字符串
        if isinstance(tags, list):
            tag_str = ", ".join(t.strip() for t in tags if t.strip())
        else:
            tag_str = str(tags).strip()
        if tag_str:
            fm_lines.append(f"tags: [{tag_str}]")

    skil_md_content = "---\n" + "\n".join(fm_lines) + "\n---\n\n" + content

    # ── 步骤 6: 创建目录并写入 SKILL.md ──
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "SKILL.md").write_text(skil_md_content, encoding="utf-8")
        logger.info("个人技能导入成功: '%s' → %s", slug, target_dir)
    except OSError as e:
        logger.exception("创建技能目录失败")
        return {"ok": False, "message": f"创建技能目录失败: {e}"}

    # ── 步骤 7: 写入附加文件 ──
    if files and isinstance(files, dict):
        for rel_path, file_content in files.items():
            try:
                clean_path = Path(rel_path)
                # 防路径穿越
                if ".." in clean_path.parts:
                    logger.warning("拒绝可疑路径（跳过）: %s", rel_path)
                    continue
                fp = target_dir / clean_path
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_text(file_content, encoding="utf-8")
                logger.debug("  写入附加文件: %s", rel_path)
            except Exception as e:
                logger.warning("写入附加文件失败: %s - %s", rel_path, e)

    return {
        "ok": True,
        "message": f"技能 '{slug}' 导入成功",
        "path": str(target_dir.resolve()),
    }


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                      aiohttp 应用工厂 & 路由注册                               ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def make_app():
    """
    创建并配置 aiohttp Web Application。

    包含:
        - CORS 中间件（允许跨域前端调用）
        - 5 个业务路由 + 1 个健康检查路由

    返回:
        aiohttp.web.Application: 已配置路由的 app 实例
    """
    try:
        from aiohttp import web
    except ImportError:
        raise RuntimeError(
            "aiohttp 未安装，请运行: pip install aiohttp"
        )

    app = web.Application()

    # ── CORS 中间件 ─────────────────────────────────────────────────────
    #  允许任意来源跨域访问（前端开发时的必要条件）
    @web.middleware
    async def cors_middleware(request, handler):
        """为所有响应添加 CORS 头，处理 OPTIONS 预检请求。"""
        if request.method == "OPTIONS":
            # 预检请求直接返回 200，由下方统一添加 CORS 头
            resp = web.Response()
        else:
            resp = await handler(request)

        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return resp

    app.middlewares.append(cors_middleware)

    # ═══════════════════════════════════════════════════════════════════════
    #  路由 1: GET /api/skill-market/list — 查询市场技能
    # ═══════════════════════════════════════════════════════════════════════
    #  Query 参数:
    #    installed  可选，"true"=已安装 / "false"=未安装 / 不传=全部
    #    visibility 可选，按可见性过滤（如 "private"、"public"）
    #
    #  工作原理: 先从后端拉市场全量数据，再用本地扫描结果做交集/差集过滤
    async def handle_list_skills(request):
        installed_param = request.query.get("installed")
        visibility_param = request.query.get("visibility", "").lower()

        market_skills = fetch_market_skills()

        # ── 按 status 过滤：仅返回状态为 active 的技能 ──
        market_skills = [s for s in market_skills if s.get("status") == "active"]

        # ── 按安装状态过滤 ──
        if installed_param is not None:
            local_skills = scan_local_skills()
            local_slugs = {s["slug"] for s in local_skills}  # 已安装的 slug 集合
            if installed_param.lower() in ("true", "1", "yes"):
                # 只保留本地已安装的
                market_skills = [s for s in market_skills if s["slug"] in local_slugs]
            elif installed_param.lower() in ("false", "0", "no"):
                # 只保留本地未安装的
                market_skills = [s for s in market_skills if s["slug"] not in local_slugs]

        # ── 按可见性过滤 ──
        if visibility_param:
            market_skills = [
                s for s in market_skills
                if s.get("visibility", "").lower() == visibility_param
            ]

        return web.json_response(build_response(market_skills))

    # ═══════════════════════════════════════════════════════════════════════
    #  路由 2: GET /api/skill-market/local — 查询本地技能
    # ═══════════════════════════════════════════════════════════════════════
    #  独立接口，不请求后端，只扫描 ~/.hermes/skills/ 目录
    async def handle_list_local(request):
        local_skills = scan_local_skills()
        visibility_param = request.query.get("visibility", "").lower()
        if visibility_param:
            local_skills = [
                s for s in local_skills
                if s.get("visibility", "").lower() == visibility_param
            ]
        return web.json_response(build_response(local_skills))

    # ═══════════════════════════════════════════════════════════════════════
    #  路由 3: GET /api/skill-market/local/{slug}/detail — 查询本地技能详情
    # ═══════════════════════════════════════════════════════════════════════
    #  返回指定技能的文件结构（目录树）和文件内容，同时从 SKILL.md 中解析完整 frontmatter。
    #  文件内容截取前 3000 字符，二进制文件自动跳过。
    async def handle_local_detail(request):
        slug = request.match_info.get("slug", "").strip()
        if not slug:
            return web.json_response(
                {"code": "400", "message": "缺少 slug 参数"},
                status=400,
            )

        # 在所有分类目录下搜索匹配 slug 的技能目录
        if not SKILLS_DIR.exists():
            return web.json_response(
                {"code": "404", "message": f"技能 '{slug}' 未安装"},
                status=404,
            )

        try:
            skill_root = None
            namespace_name = ""

            # 策略 A: 扁平结构 — skills/<slug>/ 直接作为技能目录
            flat_candidate = SKILLS_DIR / slug
            if flat_candidate.exists() and flat_candidate.is_dir() and (flat_candidate / "SKILL.md").exists():
                skill_root = flat_candidate
                namespace_name = "default"
            else:
                # 策略 B: 分类嵌套结构 — skills/<category>/<slug>/
                for category_dir in SKILLS_DIR.iterdir():
                    if not category_dir.is_dir():
                        continue
                    candidate = category_dir / slug
                    if candidate.exists() and candidate.is_dir():
                        skill_root = candidate
                        namespace_name = category_dir.name
                        break

            if skill_root is None:
                return web.json_response(
                    {"code": "404", "message": f"技能 '{slug}' 未安装"},
                    status=404,
                )

            # ── 解析 SKILL.md 完整内容（含 frontmatter 和正文） ──
            skill_md_path = skill_root / "SKILL.md"
            frontmatter = {}
            body_content = ""
            if skill_md_path.exists():
                try:
                    raw_text = skill_md_path.read_text("utf-8")
                    if raw_text.startswith("---"):
                        parts = raw_text.split("---", 2)
                        if len(parts) >= 3:
                            # 解析 YAML frontmatter 为字典
                            fm_lines = parts[1].strip().split("\n")
                            for line in fm_lines:
                                line_stripped = line.strip()
                                if ":" in line_stripped:
                                    key, _, val = line_stripped.partition(":")
                                    key = key.strip()
                                    val = val.strip().strip('"').strip("'")
                                    # 处理嵌套键（如 hermes.tags）
                                    if "." in key:
                                        parts_key = key.split(".")
                                        d = frontmatter
                                        for pk in parts_key[:-1]:
                                            if pk not in d or not isinstance(d[pk], dict):
                                                d[pk] = {}
                                            d = d[pk]
                                        d[parts_key[-1]] = val
                                    else:
                                        frontmatter[key] = val
                            body_content = parts[2].strip()
                except Exception:
                    pass

            # ── 构建文件结构树 ──
            file_tree = []
            file_contents = {}

            for root, dirs, files in sorted(os.walk(str(skill_root))):
                # 排除 __pycache__ 目录
                dirs[:] = sorted([d for d in dirs if d != "__pycache__"])
                rel_dir = os.path.relpath(root, str(skill_root)).replace("\\", "/")
                dir_node = "" if rel_dir == "." else rel_dir

                for fname in sorted(files):
                    if fname == "__pycache__":
                        continue
                    rel_path = f"{dir_node}/{fname}" if dir_node else fname
                    file_path = os.path.join(root, fname)
                    try:
                        fsize = os.path.getsize(file_path)
                    except OSError:
                        fsize = 0

                    entry = {
                        "path": rel_path,
                        "size": fsize,
                    }

                    # 尝试读取文本文件内容（限制 3000 字符）
                    is_text = False
                    if fname.endswith((".md", ".py", ".json", ".yaml", ".yml", ".toml",
                                        ".cfg", ".ini", ".conf", ".txt", ".env", ".csv",
                                        ".xml", ".html", ".css", ".js", ".sh", ".bat",
                                        ".ps1", ".tf", ".dockerfile", ".gitignore")):
                        is_text = True
                    elif fname == "SKILL.md":
                        is_text = True
                    elif "." not in fname:
                        # 无扩展名文件（如 Dockerfile）也尝试读取
                        is_text = True

                    if is_text and fsize <= 500_000:
                        try:
                            with open(file_path, "r", encoding="utf-8") as fh:
                                content = fh.read(3000)
                            file_contents[rel_path] = content
                        except Exception:
                            pass

                    file_tree.append(entry)

            # ── 组装响应 ──
            detail = {
                "slug": slug,
                "name": frontmatter.get("name", slug),
                "description": frontmatter.get("description", ""),
                "visibility": frontmatter.get("visibility", "personal"),
                "version": frontmatter.get("version", ""),
                "author": frontmatter.get("author", ""),
                "namespaceName": namespace_name,
                "tags": frontmatter.get("tags", []),
                "frontmatter": frontmatter,
                "body": body_content,
                "fileTree": file_tree,
                "fileContents": file_contents,
                "readmeSize": len(body_content),
                "fileCount": len(file_tree),
            }

            return web.json_response({
                "code": "0000",
                "message": "成功",
                "data": detail,
            })

        except Exception as e:
            logger.exception("handle_local_detail 异常")
            return web.json_response(
                {"code": "500", "message": f"查询失败: {e}"},
                status=500,
            )

    # ═══════════════════════════════════════════════════════════════════════
    #  路由 3: GET /api/skill-market/skills/{skillId}/versions/{versionId}/download
    #         代理下载技能 ZIP
    # ═══════════════════════════════════════════════════════════════════════
    #  直接转发后端 ZIP 流给前端，服务端不做磁盘缓存
    async def handle_download(request):
        skill_id = request.match_info.get("skillId", "").strip()
        version_id = request.match_info.get("versionId", "").strip()

        if not skill_id or not version_id:
            return web.json_response(
                {"code": "400", "message": "缺少 skillId 或 versionId 参数"},
                status=400,
            )

        # 构造后端下载地址
        url = f"{SKILLHUB_URL}/client/skills/{quote(skill_id)}/versions/{quote(version_id)}/download"
        headers = _build_auth_headers()

        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=60) as resp:
                if resp.status != 200:
                    return web.json_response(
                        {"code": str(resp.status), "message": f"下载失败: HTTP {resp.status}"},
                        status=resp.status,
                    )
                zip_data = resp.read()

                # 尝试从后端响应头获取文件名，fallback 到默认命名
                content_disposition = resp.headers.get("Content-Disposition", "")
                filename = f"skill_{skill_id}_{version_id}.zip"
                if content_disposition and "filename=" in content_disposition:
                    try:
                        filename = content_disposition.split("filename=")[1].strip('"').strip("'")
                    except Exception:
                        pass

                return web.Response(
                    body=zip_data,
                    content_type="application/zip",
                    headers={
                        "Content-Disposition": f'attachment; filename="{filename}"',
                    },
                )
        except Exception as e:
            logger.exception("handle_download 异常")
            return web.json_response(
                {"code": "500", "message": f"下载失败: {e}"},
                status=500,
            )

    # ═══════════════════════════════════════════════════════════════════════
    #  路由 4: POST /api/skill-market/install — 安装技能
    # ═══════════════════════════════════════════════════════════════════════
    #  请求体 JSON: {"skillId": "...", "versionId"?: "...", "version"?: "..."}
    #  响应: {"ok": true/false, "message": "..."}
    async def handle_install(request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                {"ok": False, "message": "请求体必须是 JSON"}, status=400
            )

        skill_id = body.get("skillId", "").strip()
        if not skill_id:
            return web.json_response(
                {"ok": False, "message": "缺少 skillId 参数"}, status=400
            )

        version_id = body.get("versionId")
        version = body.get("version")

        result = install_skill(skill_id, version_id=version_id, version=version)
        status = 200 if result["ok"] else 400
        return web.json_response(result, status=status)

    # ═══════════════════════════════════════════════════════════════════════
    #  路由 5: POST /api/skill-market/uninstall — 卸载技能
    # ═══════════════════════════════════════════════════════════════════════
    #  请求体 JSON: {"slug": "..."}
    #  响应: {"ok": true/false, "message": "..."}
    async def handle_uninstall(request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                {"ok": False, "message": "请求体必须是 JSON"}, status=400
            )

        slug = body.get("slug", "").strip()
        if not slug:
            return web.json_response(
                {"ok": False, "message": "缺少 slug 参数"}, status=400
            )

        result = uninstall_skill(slug)
        status = 200 if result["ok"] else 404
        return web.json_response(result, status=status)

    # ═══════════════════════════════════════════════════════════════════════
    #  路由 6: POST /api/skill-market/import-local — 导入个人技能
    # ═══════════════════════════════════════════════════════════════════════
    #  请求体 JSON: 参考 import_local_skill() 参数说明
    #  响应: {"ok": true/false, "message": "...", "path": "..."}
    async def handle_import_local(request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                {"ok": False, "message": "请求体必须是 JSON"}, status=400
            )

        if not isinstance(body, dict):
            return web.json_response(
                {"ok": False, "message": "请求体必须是 JSON 对象"}, status=400
            )

        result = import_local_skill(
            name=body.get("name", ""),
            display_name=body.get("displayName", ""),
            description=body.get("description", ""),
            category=body.get("category", ""),
            visibility=body.get("visibility", "personal"),
            version=body.get("version", ""),
            author=body.get("author", ""),
            tags=body.get("tags"),
            content=body.get("content", ""),
            files=body.get("files"),
        )
        status = 200 if result["ok"] else 400
        return web.json_response(result, status=status)

    # ═══════════════════════════════════════════════════════════════════════
    #  路由 7: GET /health — 健康检查
    # ═══════════════════════════════════════════════════════════════════════
    async def handle_health(request):
        return web.json_response({
            "status": "ok",
            "service": "hermes-skill-market-api",
            "backend": SKILLHUB_URL,
        })

    # ── 路由注册表 ──────────────────────────────────────────────────────
    app.router.add_get("/api/skill-market/list", handle_list_skills)
    app.router.add_get("/api/skill-market/local", handle_list_local)
    app.router.add_get("/api/skill-market/local/{slug}/detail", handle_local_detail)
    app.router.add_get(
        "/api/skill-market/skills/{skillId}/versions/{versionId}/download",
        handle_download,
    )
    app.router.add_post("/api/skill-market/install", handle_install)
    app.router.add_post("/api/skill-market/uninstall", handle_uninstall)
    app.router.add_post("/api/skill-market/import-local", handle_import_local)
    app.router.add_get("/health", handle_health)

    return app


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                              入口: 直接运行                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

if __name__ == "__main__":
    from aiohttp import web

    # 端口优先级: 命令行参数 > 环境变量 SKILL_API_PORT > 默认 8643
    PORT = (
        int(sys.argv[1]) if len(sys.argv) > 1
        else int(os.environ.get("SKILL_API_PORT", 8643))
    )
    HOST = os.environ.get("SKILL_API_HOST", "127.0.0.1")

    app = make_app()

    # 启动横幅
    print(f"┌───────────────────────────────────────────────┐")
    print(f"│  Hermes Skill Market API Server (Standalone)  │")
    print(f"│  {HOST}:{PORT}                                      │")
    print(f"│                                               │")
    print(f"│  API 接口:                                     │")
    print(f"│  GET  /api/skill-market/list           市场查询 │")
    print(f"│  GET  /api/skill-market/local          本地查询 │")
    print(f"│  GET  /api/skill-market/local/{'{slug}'}/detail  详情查询 │")
    print(f"│  GET  /api/skill-market/.../download    下载代理 │")
    print(f"│  POST /api/skill-market/install         安装技能 │")
    print(f"│  POST /api/skill-market/uninstall       卸载技能 │")
    print(f"│  POST /api/skill-market/import-local    导入个人技能 │")
    print(f"│  GET  /health                           健康检查 │")
    print(f"│                                               │")
    print(f"│  后端地址: {SKILLHUB_URL:<35s} │")
    print(f"│  本地技能: {str(SKILLS_DIR):<35s} │")
    print(f"└───────────────────────────────────────────────┘")

    web.run_app(app, host=HOST, port=PORT)
