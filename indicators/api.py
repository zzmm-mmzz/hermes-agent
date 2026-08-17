"""indicators/api.py - 指标管理 & 执行 API（挂载进主网关）

按主网关的写法（与 hub_api_server.py 相同的 make_app() 模式），
由 gateway/platforms/api_server.py 启动时挂载路由。

接口:
    GET  /api/indicators              指标列表（后端 t_indicator + 本地 applied 状态）
    GET  /api/indicators/applied      本地已应用指标列表
    POST /api/indicators/apply        应用指标到本地（{code}）
    POST /api/indicators/unapply      取消应用（{code}）
    POST /api/indicators/query        执行指标查询（{login_name, codes}）
    GET  /health                      健康检查
"""
import json
import logging
from urllib import request as urllib_request
from urllib.error import URLError

from aiohttp import web

from indicators import engine, loader
from indicators.config import CONFIG

logger = logging.getLogger(__name__)

BACKEND_URL = CONFIG["backend_base_url"]
BACKEND_PREFIX = CONFIG["backend_api_prefix"]


# ── 后端 t_indicator 访问 ────────────────────────────────────────────────

def _backend_get(path: str, timeout: int = 15):
    """GET 后端接口，返回 JSON（None=失败）。"""
    url = f"{BACKEND_URL}{BACKEND_PREFIX}{path}"
    try:
        with urllib_request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else None
    except Exception as e:
        logger.warning("backend GET %s failed: %s", url, e)
        return None


def _backend_post(path: str, payload: dict, timeout: int = 15):
    """POST 后端接口，返回 JSON（None=失败）。"""
    url = f"{BACKEND_URL}{BACKEND_PREFIX}{path}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib_request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else None
    except URLError as e:
        error_body = ""
        if hasattr(e, "read"):
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                pass
        logger.warning("backend POST %s failed: %s %s", url, e, error_body)
        return None
    except Exception as e:
        logger.warning("backend POST %s failed: %s", url, e)
        return None


def _list_from_backend() -> list:
    """从后端 t_indicator 拉全量指标（分页循环，每页 100）。"""
    items = []
    page = 1
    while True:
        data = _backend_get(f"/list?pageNum={page}&pageSize=100")
        if not data:
            break
        inner = data.get("data") or {}
        records = inner.get("records") or inner.get("list") or []
        items.extend(records)
        total = inner.get("total", 0)
        if page * 100 >= total or not records:
            break
        page += 1
    return items


def _detail_from_backend(code: str) -> dict:
    """从后端拉单个指标详情（含脚本全文）。"""
    data = _backend_get(f"/detail?code={code}")
    if not data:
        return {}
    inner = data.get("data") or {}
    return inner if isinstance(inner, dict) else {}


# ── make_app ──────────────────────────────────────────────────────────────

def make_app():
    app = web.Application()

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

    # ── 接口 1: 指标列表（后端 + applied 状态）──
    async def get_indicators(request):
        try:
            items = _list_from_backend()
        except Exception as e:
            logger.exception("list indicators failed")
            items = []

        for item in items:
            code = str(item.get("code", ""))
            item["applied"] = bool(code) and loader.is_applied(code)

        # applied 过滤
        filter_applied = request.query.get("applied")
        if filter_applied is not None:
            want = filter_applied.lower() in ("true", "1", "yes")
            items = [i for i in items if i.get("applied") == want]

        return web.json_response({"indicators": items, "total": len(items)})

    # ── 接口 2: 本地已应用列表 ──
    async def get_applied_indicators(request):
        meta = loader.list_metadata()
        for item in meta:
            item["applied"] = True
            item["script_exists"] = loader.script_path(item["code"]).exists()
        return web.json_response({"indicators": meta, "total": len(meta)})

    # ── 接口 3: 应用指标 ──
    async def apply_indicator(request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "message": "请求体必须是 JSON"}, status=400)

        code = str(body.get("code", "")).strip()
        if not code:
            return web.json_response({"ok": False, "message": "缺少 code 参数"}, status=400)

        detail = _detail_from_backend(code)
        if not detail:
            return web.json_response(
                {"ok": False, "message": f"后端未找到指标 {code}"}, status=404
            )

        script = detail.get("script") or ""
        if not script:
            return web.json_response(
                {"ok": False, "message": f"指标 {code} 无脚本内容，无法应用"}, status=400
            )

        result = loader.apply_script(
            code=code,
            name=detail.get("name") or code,
            script=script,
            url=detail.get("url"),
            method=detail.get("method") or "POST",
            version=str(detail.get("version") or "1.0"),
            sort_order=int(detail.get("sortOrder") or 99),
        )
        status = 200 if result["ok"] else 400
        return web.json_response(result, status=status)

    # ── 接口 4: 取消应用 ──
    async def unapply_indicator(request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "message": "请求体必须是 JSON"}, status=400)

        code = str(body.get("code", "")).strip()
        if not code:
            return web.json_response({"ok": False, "message": "缺少 code 参数"}, status=400)

        result = loader.unapply_script(code)
        return web.json_response(result, status=200)

    # ── 接口 5: 执行指标查询（真实数据）──
    async def query_indicators(request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "message": "请求体必须是 JSON"}, status=400)

        login_name = str(body.get("login_name", "")).strip()
        if not login_name:
            return web.json_response({"ok": False, "message": "缺少 login_name 参数"}, status=400)

        codes = body.get("codes")
        if codes is None:
            codes = list(engine.INDICATOR_DEFS.keys())
        elif isinstance(codes, str):
            codes = [codes]
        elif isinstance(codes, list):
            codes = [str(c) for c in codes]

        # 校验 codes 都存在
        unknown = [c for c in codes if c not in engine.INDICATOR_DEFS]
        if unknown:
            return web.json_response(
                {"ok": False, "message": f"未注册的指标: {unknown}"}, status=400
            )

        try:
            # 查询是同步阻塞的（urllib），放到线程池避免卡事件循环
            result = await request.app.loop.run_in_executor(
                None, engine.run_query_core_indicators, login_name, codes
            )
            return web.json_response(
                {"ok": True, "data": json.loads(result)}, status=200
            )
        except Exception as e:
            logger.exception("query indicators failed")
            return web.json_response({"ok": False, "message": f"查询失败: {e}"}, status=500)

    # ── 路由注册 ──
    app.router.add_get("/api/indicators", get_indicators)
    app.router.add_get("/api/indicators/applied", get_applied_indicators)
    app.router.add_post("/api/indicators/apply", apply_indicator)
    app.router.add_post("/api/indicators/unapply", unapply_indicator)
    app.router.add_post("/api/indicators/query", query_indicators)

    async def health(request):
        return web.json_response({"status": "ok", "service": "indicators-api"})

    app.router.add_get("/health", health)

    return app


def init() -> None:
    """初始化：注册内置指标 + 扫描加载脚本指标。网关启动时调用。"""
    engine.register_builtin_indicators()
    results = loader.scan_and_load_all()
    loaded = sum(1 for r in results.values() if r.get("ok"))
    if results:
        logger.info("indicators: %d/%d script indicators loaded", loaded, len(results))
