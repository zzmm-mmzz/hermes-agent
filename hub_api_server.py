"""
Hermes SkillHub API Server
提供五个接口供 Hermes Desktop 前端调用，与自建 SkillHub 集成。
启动: python hub_api_server.py
端口: 8642
"""

import json
import io
import zipfile
import os
import sys
import logging
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import quote

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("hub-api")

# ── 配置 ──────────────────────────────────────────────────────────
HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
SKILLS_DIR = HERMES_HOME / "skills"

# 从 hub_config.yaml 读取配置
HUB_CONFIG_PATH = Path(__file__).parent / "hub_config.yaml"

def _load_hub_config() -> dict:
    """从 hub_config.yaml 读取配置."""
    import yaml
    try:
        if HUB_CONFIG_PATH.exists():
            with open(HUB_CONFIG_PATH, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning("Failed to load hub_config.yaml: %s", e)
    return {}


def _load_skillhub_config() -> dict:
    """从 hub_config.yaml 中读取 SkillHub 完整配置（base_url + auth + upload）。"""
    cfg = _load_hub_config().get("skillhub", {})
    return {
        "base_url": cfg.get("base_url", "http://localhost:8080/api/v1"),
        "username": cfg.get("username", "local-admin"),
        "password": cfg.get("password", ""),
        "upload": cfg.get("upload", {}),
    }


def _load_skillhub_auth() -> dict:
    """从 hub_config.yaml 中读取 SkillHub 认证配置."""
    sc = _load_hub_config().get("skillhub", {})
    return {
        "username": sc.get("username", "local-admin"),
        "password": sc.get("password", ""),
    }


def _load_server_config() -> dict:
    """从 hub_config.yaml 中读取服务器配置."""
    cfg = _load_hub_config()
    sc = cfg.get("server", {})
    return {
        "host": sc.get("host", "127.0.0.1"),
        "port": int(sc.get("port", 8642)),
    }


# 读取 SkillHub base_url（由 hub_config.yaml 控制），后续直接使用
SKILLHUB_URL = _load_skillhub_config()["base_url"]

# ── SkillHub 工具函数 ──────────────────────────────────────────────

def _fetch_json(url: str, timeout: int = 20):
    """GET JSON from SkillHub via urllib."""
    try:
        with urlopen(url, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.warning("fetch_json failed: %s - %s", url, e)
        return None


def _fetch_bytes(url: str, timeout: int = 30):
    """GET raw bytes from SkillHub."""
    try:
        with urlopen(url, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return resp.read()
    except Exception as e:
        logger.warning("fetch_bytes failed: %s - %s", url, e)
        return None


def _build_auth_headers() -> dict:
    """
    根据配置构建 SkillHub 认证请求头.
    - local 模式: X-Mock-User-Id
    - 生产模式 (有密码): 先登录拿 session
    """
    auth = _load_skillhub_auth()
    username = auth["username"]
    password = auth["password"]

    if not password:
        # local 模式，直接使用 mock header
        return {"X-Mock-User-Id": username}

    # 有密码 → 尝试 direct login
    try:
        login_data = json.dumps({"username": username, "password": password}).encode()
        req = Request(
            f"{SKILLHUB_URL}/auth/direct/login",
            data=login_data,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            # 返回的 session 信息可能在不同版本不同，尝试提取 token/cookie
            logger.info("SkillHub login success for user '%s'", username)
            # 返回 cookie 或 token
            set_cookie = resp.headers.get("Set-Cookie", "")
            if set_cookie:
                return {"Cookie": set_cookie}
            token = body.get("token") or body.get("accessToken") or ""
            if token:
                return {"Authorization": f"Bearer {token}"}
    except Exception as e:
        logger.warning("SkillHub direct login failed, falling back to mock auth: %s", e)

    # fallback
    return {"X-Mock-User-Id": username}


def _hub_post_multipart(url: str, fields: dict, file_data: bytes, file_name: str) -> dict:
    """
    向 SkillHub 发送 multipart/form-data POST 请求.
    使用 urllib 构建 multipart 请求体。
    """
    import uuid
    boundary = uuid.uuid4().hex

    body_parts = []
    for key, value in fields.items():
        body_parts.append(f"--{boundary}\r\n")
        body_parts.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n')
        body_parts.append(f"{value}\r\n")

    body_parts.append(f"--{boundary}\r\n")
    body_parts.append(f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n')
    body_parts.append("Content-Type: application/zip\r\n\r\n")
    body_parts.append(file_data.decode("latin-1") if isinstance(file_data, (bytes, bytearray)) else file_data)
    body_parts.append(f"\r\n--{boundary}--\r\n")

    body = "".join(body_parts).encode("latin-1")

    headers = _build_auth_headers()
    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"

    try:
        req = Request(url, data=body, headers=headers)
        with urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return {"ok": True, "status": resp.status, "response": result}
    except Exception as e:
        logger.error("hub_post_multipart failed: %s", e)
        # 尝试读取错误响应体
        try:
            if hasattr(e, 'read'):
                err_body = e.read().decode("utf-8")
                return {"ok": False, "message": str(e), "detail": err_body}
        except Exception:
            pass
        return {"ok": False, "message": str(e)}


def list_hub_skills():
    """返回 SkillHub 上所有技能列表."""
    url = f"{SKILLHUB_URL}/skills?limit=200"
    data = _fetch_json(url)
    if not data:
        return []
    items = data.get("items", [])
    results = []
    for item in items:
        slug = item.get("slug", "")
        if not slug:
            continue
        results.append({
            "slug": slug,
            "name": item.get("displayName") or item.get("name") or slug,
            "description": item.get("summary") or "",
            "version": item.get("latestVersion", {}).get("version", "1.0.0"),
            "tags": list(item.get("tags", {}).keys()) if isinstance(item.get("tags"), dict) else [],
        })
    return results


def list_installed_skills():
    """扫描 ~/.hermes/skills/ 返回已安装技能列表."""
    if not SKILLS_DIR.exists():
        return []
    results = []
    try:
        for category_dir in sorted(SKILLS_DIR.iterdir()):
            if not category_dir.is_dir():
                continue
            category = category_dir.name
            for skill_dir in sorted(category_dir.iterdir()):
                if not skill_dir.is_dir():
                    continue
                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue
                # 读 frontmatter 取 name/description
                name = skill_dir.name
                description = ""
                try:
                    content = skill_file.read_text("utf-8")[:4000]
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
                except Exception:
                    pass
                results.append({
                    "name": name,
                    "slug": skill_dir.name,
                    "description": description,
                    "category": category,
                    "path": str(skill_dir),
                })
    except Exception as e:
        logger.error("scan installed skills error: %s", e)
    return results


def install_hub_skill(slug: str, version: str = None) -> dict:
    """
    从 SkillHub 下载技能并安装到 ~/.hermes/skills/.
    返回 {"ok": True/False, "message": "..."}
    """
    # 先查技能详情，获取版本号
    detail_url = f"{SKILLHUB_URL}/skills/{quote(slug)}"
    detail = _fetch_json(detail_url)
    if detail is None:
        return {"ok": False, "message": f"技能 '{slug}' 在 SkillHub 上未找到"}

    latest_version = detail.get("latestVersion", {})
    ver = version or latest_version.get("version", "1.0.0")
    display_name = detail.get("skill", {}).get("displayName") or slug

    # 下载 ZIP
    download_url = f"{SKILLHUB_URL}/download?slug={quote(slug)}&version={ver}"
    raw = _fetch_bytes(download_url)
    if raw is None:
        return {"ok": False, "message": f"下载技能 '{slug}' 失败"}

    # 解析 ZIP
    files: dict[str, str] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                if info.file_size > 500_000:
                    continue
                try:
                    files[info.filename] = zf.read(info.filename).decode("utf-8")
                except (UnicodeDecodeError, KeyError):
                    continue
    except zipfile.BadZipFile:
        return {"ok": False, "message": "下载的文件不是有效的 ZIP"}

    if not files:
        return {"ok": False, "message": "ZIP 中没有有效文件"}

    # 确定 category
    skill_info = detail.get("skill", {})
    tags = skill_info.get("tags", {})
    if isinstance(tags, dict) and tags:
        category = list(tags.keys())[0]
    elif isinstance(tags, list) and tags:
        category = tags[0] if tags else "self-hosted"
    else:
        category = "self-hosted"

    # 写入 ~/.hermes/skills/<category>/<slug>/
    target_dir = SKILLS_DIR / category / slug
    target_dir.mkdir(parents=True, exist_ok=True)

    for rel_path, content in files.items():
        clean_path = Path(rel_path)
        if ".." in clean_path.parts:
            continue
        file_path = target_dir / clean_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    logger.info("Installed skill '%s' (v%s) to %s", slug, ver, target_dir)
    return {"ok": True, "message": f"技能 '{display_name}' 安装成功 (v{ver})"}


def uninstall_skill(slug: str) -> dict:
    """
    从 ~/.hermes/skills/ 卸载技能.
    在所有分类目录下搜索匹配的技能目录。
    """
    if not SKILLS_DIR.exists():
        return {"ok": False, "message": f"技能 '{slug}' 未安装"}

    removed = False
    for category_dir in SKILLS_DIR.iterdir():
        if not category_dir.is_dir():
            continue
        skill_dir = category_dir / slug
        if skill_dir.exists() and skill_dir.is_dir():
            import shutil
            shutil.rmtree(skill_dir)
            logger.info("Uninstalled skill '%s' from %s", slug, category_dir)
            removed = True

    if removed:
        return {"ok": True, "message": f"技能 '{slug}' 卸载成功"}
    else:
        return {"ok": False, "message": f"技能 '{slug}' 未安装"}


def publish_skill_to_hub(zip_data: bytes, file_name: str) -> dict:
    """
    将 ZIP 包发布到 SkillHub，public 可见。
    """
    url = f"{SKILLHUB_URL}/publish"
    fields = {
        "namespace": "global",
        "visibility": "PUBLIC",
        "confirmWarnings": "true",
    }
    result = _hub_post_multipart(url, fields, zip_data, file_name)
    return result


# ── HTTP Server ────────────────────────────────────────────────────

def make_app():
    try:
        from aiohttp import web
    except ImportError:
        raise RuntimeError("aiohttp not installed; run: pip install aiohttp")

    app = web.Application()

    # CORS 中间件
    @web.middleware
    async def cors_middleware(request, handler):
        if request.method == "OPTIONS":
            resp = web.Response()
        else:
            resp = await handler(request)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return resp

    app.middlewares.append(cors_middleware)

    # ── 接口 1: 获取所有技能列表 ──
    async def get_all_skills(request):
        skills = list_hub_skills()
        installed = {s["slug"] for s in list_installed_skills()}
        for s in skills:
            s["installed"] = s["slug"] in installed

        # 可选 installed 参数过滤
        filter_installed = request.query.get("installed")
        if filter_installed is not None:
            if filter_installed.lower() in ("true", "1", "yes"):
                skills = [s for s in skills if s["installed"]]
            elif filter_installed.lower() in ("false", "0", "no"):
                skills = [s for s in skills if not s["installed"]]

        return web.json_response({"skills": skills, "total": len(skills)})

    # ── 接口 2: 获取已安装技能列表 ──
    async def get_installed_skills(request):
        skills = list_installed_skills()
        return web.json_response({"skills": skills, "total": len(skills)})

    # ── 接口 3: 安装技能 ──
    async def install_skill(request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "message": "请求体必须是 JSON"}, status=400)

        slug = body.get("slug", "").strip()
        if not slug:
            return web.json_response({"ok": False, "message": "缺少 slug 参数"}, status=400)

        installed = list_installed_skills()
        if any(s["slug"] == slug for s in installed):
            return web.json_response({"ok": False, "message": f"技能 '{slug}' 已安装"}, status=409)

        version = body.get("version")
        result = install_hub_skill(slug, version)
        status = 200 if result["ok"] else 500
        return web.json_response(result, status=status)

    # ── 接口 4: 卸载技能 ──
    async def uninstall_skill_handler(request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "message": "请求体必须是 JSON"}, status=400)

        slug = body.get("slug", "").strip()
        if not slug:
            return web.json_response({"ok": False, "message": "缺少 slug 参数"}, status=400)

        result = uninstall_skill(slug)
        status = 200 if result["ok"] else 404
        return web.json_response(result, status=status)

    # ── 接口 5: 上传技能到 SkillHub ──
    async def upload_skill(request):
        """
        接受 ZIP 文件上传，发布到 SkillHub.
        支持: multipart/form-data (file 字段) 或 JSON body 中的 base64 数据
        """
        try:
            content_type = request.content_type or ""

            if "multipart" in content_type:
                # multipart 上传
                reader = await request.multipart()
                field = await reader.next()
                if not field or field.name != "file":
                    return web.json_response({"ok": False, "message": "缺少 file 字段"}, status=400)

                file_name = field.filename or "skill.zip"
                zip_data = await field.read()
            else:
                # JSON body: { "file": "<base64>", "fileName": "skill.zip" }
                try:
                    body = await request.json()
                except Exception:
                    return web.json_response({"ok": False, "message": "请求体必须是 JSON 或 multipart/form-data"}, status=400)

                b64_data = body.get("file", "")
                if not b64_data:
                    return web.json_response({"ok": False, "message": "缺少 file 字段 (base64)"}, status=400)

                import base64
                try:
                    zip_data = base64.b64decode(b64_data)
                except Exception:
                    return web.json_response({"ok": False, "message": "file 不是有效的 base64"}, status=400)

                file_name = body.get("fileName", "skill.zip")

            if not zip_data or len(zip_data) < 10:
                return web.json_response({"ok": False, "message": "文件内容为空"}, status=400)

            result = publish_skill_to_hub(zip_data, file_name)
            status = 200 if result.get("ok") else 500
            return web.json_response(result, status=status)
        except Exception as e:
            logger.exception("upload_skill error")
            return web.json_response({"ok": False, "message": f"服务器内部错误: {e}"}, status=500)

    # ── 注册路由 ──
    app.router.add_get("/api/skills", get_all_skills)
    app.router.add_get("/api/skills/installed", get_installed_skills)
    app.router.add_post("/api/skills/install", install_skill)
    app.router.add_post("/api/skills/uninstall", uninstall_skill_handler)
    app.router.add_post("/api/skills/upload", upload_skill)

    # 健康检查
    async def health(request):
        return web.json_response({"status": "ok", "service": "hermes-hub-api"})

    app.router.add_get("/health", health)

    return app


if __name__ == "__main__":
    from aiohttp import web

    # 优先用命令行参数指定端口，否则从配置读取，默认 8642
    if len(sys.argv) > 1:
        PORT = int(sys.argv[1])
    else:
        PORT = _load_server_config()["port"]

    HOST = _load_server_config()["host"]
    app = make_app()
    print(f"┌─────────────────────────────────────────┐")
    print(f"│  Hermes SkillHub API Server            │")
    print(f"│  {HOST}:{PORT}                               │")
    print(f"│                                         │")
    print(f"│  GET  /api/skills         全部技能      │")
    print(f"│  GET  /api/skills/installed 已安装技能  │")
    print(f"│  POST /api/skills/install  安装技能     │")
    print(f"│  POST /api/skills/uninstall 卸载技能   │")
    print(f"│  POST /api/skills/upload   上传技能     │")
    print(f"└─────────────────────────────────────────┘")
    web.run_app(app, host=HOST, port=PORT)
