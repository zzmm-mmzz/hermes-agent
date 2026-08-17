"""indicators/engine.py - 指标查询引擎（从 mcp-core-indicators/server.py 迁移）

保留原 MCP 的完整查询链路：
  Step 1: fetch_base_org_id   - 按登录名获取 baseOrgId
  Step 2: fetch_org_no        - 按 baseOrgId 获取 org_no
  Step 3: query_indicators_by_codes - 按 codes 分组查询（批量 counts / 独立请求）
  标准化解析 parse_indicator_to_standard -> {code, value?, unit?, trend?, error?}

与原来不同：
  - 配置抽到 indicators/config.toml（平台地址、认证、area.js 路径、缓存开关）
  - INDICATOR_DEFS 注册表由 loader.py 动态维护（内置 + 脚本），本模块只提供引擎函数
  - 去掉 MCP HTTP 层，纯函数引擎
"""
import hashlib
import json
import logging
import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib import request as urllib_request
from urllib.error import URLError

from indicators.config import CONFIG

logger = logging.getLogger(__name__)

API_BASE_URL = CONFIG["platform_base_url"]
AUTH_MODE = CONFIG.get("auth_mode", "login_md5")
CACHE_LOGIN_CONTEXT = CONFIG.get("cache_login_context", True)

# ── 指标定义注册表（由 loader 填充）───────────────────────────────────
# 条目结构: {code: {"name", "url", "method", "build_params", "parse_result",
#                   "parse_to_standard", "sortOrder", "from_script"}}
INDICATOR_DEFS: Dict[str, dict] = {}


# ── 辅助函数 ──────────────────────────────────────────────────────────────

def _compute_org_lev(org_no: str) -> str:
    """Compute org_lev based on org_no value."""
    if org_no == "43101":
        return "1"
    elif len(org_no) == 5:
        return "5"
    else:
        return "6"


def _truncate_org_no(org_no: str) -> str:
    """Truncate org_no: if length > 7, take first 7 chars."""
    if len(org_no) > 7:
        return org_no[:7]
    return org_no


def _get_today_ds() -> str:
    """Get today's date as YYYYMMDD string."""
    return datetime.now().strftime("%Y%m%d")


def _get_last_month_ym() -> str:
    """Get last month as YYYYMM string."""
    now = datetime.now()
    first = now.replace(day=1)
    if first.month > 1:
        last = first.replace(month=first.month - 1)
    else:
        last = first.replace(year=first.year - 1, month=12)
    return last.strftime("%Y%m")


def _get_ago_month_ym() -> str:
    """Get the same month last year as YYYYMM string."""
    now = datetime.now()
    first = now.replace(day=1)
    if first.month > 1:
        last = first.replace(month=first.month - 1)
    else:
        last = first.replace(year=first.year - 1, month=12)
    ago = last.replace(year=last.year - 1)
    return ago.strftime("%Y%m")


# ── HTTP 工具 ──────────────────────────────────────────────────────────────

def _http_get(url: str, headers: dict = None, timeout: int = 30) -> dict:
    """Synchronous HTTP GET, returns parsed JSON."""
    req = urllib_request.Request(url, headers=headers or {})
    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except Exception as e:
        raise RuntimeError(f"GET {url} failed: {e}")


def _http_post(url: str, data: Any, headers: dict = None, timeout: int = 30) -> dict:
    """Synchronous HTTP POST with JSON body, returns raw response dict."""
    body_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req_headers = headers or {}
    req_headers.setdefault("Content-Type", "application/json")
    req = urllib_request.Request(url, data=body_bytes, headers=req_headers, method="POST")
    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8")
            return {
                "status_code": resp.status,
                "data": json.loads(resp_body) if resp_body else {},
            }
    except URLError as e:
        error_body = ""
        if hasattr(e, "read"):
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                pass
        return {
            "status_code": getattr(e, "code", 0),
            "data": json.loads(error_body) if error_body else {},
            "error": str(e),
        }
    except Exception as e:
        return {"status_code": 0, "data": {}, "error": str(e)}


def _auth_headers(login_name: str) -> dict:
    """按配置的认证模式构造请求头。"""
    headers = {"login-name": login_name, "Content-Type": "application/json"}
    if AUTH_MODE == "login_md5":
        headers["Authorization"] = hashlib.md5(login_name.encode()).hexdigest()
    return headers


# ── 默认参数构造器（内置指标通用逻辑）─────────────────────────────────

def _build_params_default(code: str, ctx: dict) -> dict:
    """默认参数：org_lev/org_no + 分页，适用于 url=None 的批量 counts 指标。"""
    return {
        "code": code,
        "param": {
            "org_lev": ctx["org_lev"],
            "org_no": ctx["org_no"],
            "pageNum": "1",
            "pageSize": "40",
        },
    }


def _build_params_common_counts(code: str, ctx: dict) -> dict:
    """与默认一致（10029b 等批量 counts 指标）。"""
    return _build_params_default(code, ctx)


def _build_params_10030(code: str, ctx: dict) -> dict:
    """当日报修次数：ds + idx_no + idx_typ 等参数。"""
    return {
        "code": code,
        "param": {
            "org_lev": ctx["org_lev"],
            "org_no": ctx["org_no"],
            "ds": ctx["ds"],
            "idx_no": "10030",
            "idx_typ": "0",
            "pageNum": "1",
            "pageSize": "40",
        },
    }


def _build_params_10020(code: str, ctx: dict) -> dict:
    """综合线损率：dt + ago_dt 双日期。"""
    return {
        "code": code,
        "param": {
            "org_lev": ctx["org_lev"],
            "org_no": ctx["org_no"],
            "dt": ctx["ds"],
            "ago_dt": ctx["ago_month_ym"],
            "pageNum": "1",
            "pageSize": "40",
        },
    }


def _build_params_67851(code: str, ctx: dict) -> dict:
    """安全运行天数（独立 GET /plan/safeConfig/selectSafeDayByOrgCode）。"""
    return {
        "org_lev": ctx["org_lev"],
        "org_no": ctx["org_no"],
        "pageNum": "1",
        "pageSize": "40",
    }


BUILTIN_BUILD_PARAMS: Dict[str, Any] = {
    "10029b": _build_params_common_counts,
    "10030": _build_params_10030,
    "10020": _build_params_10020,
    "20016": _build_params_common_counts,
    "10012": _build_params_default,
    "67851": _build_params_67851,
}


def register_builtin_indicators() -> None:
    """注册内置指标定义（10029b/10030/10020/20016/10012/67851）。"""
    builtins = {
        "10029b": {"name": "台区实时停电数", "url": None, "method": "POST", "sortOrder": 1},
        "10030": {"name": "当日报修次数", "url": None, "method": "POST", "sortOrder": 2},
        "10020": {"name": "综合线损率", "url": None, "method": "POST", "sortOrder": 3},
        "20016": {"name": "低电压用户数", "url": None, "method": "POST", "sortOrder": 4},
        "10012": {"name": "实时负荷", "url": None, "method": "POST", "sortOrder": 5},
        "67851": {"name": "安全运行天数", "url": "/plan/safeConfig/selectSafeDayByOrgCode",
                  "method": "GET", "sortOrder": 7},
    }
    for code, meta in builtins.items():
        if code in INDICATOR_DEFS:
            continue
        INDICATOR_DEFS[code] = {
            "name": meta["name"],
            "url": meta["url"],
            "method": meta.get("method", "POST"),
            "build_params": BUILTIN_BUILD_PARAMS.get(code, _build_params_default),
            "parse_result": None,
            "parse_to_standard": None,
            "sortOrder": meta["sortOrder"],
            "from_script": False,
        }


# ── 参数构造 & 解析（注册表驱动）──────────────────────────────────────

def get_build_params(code: str, ctx: dict) -> Optional[dict]:
    """根据 code 返回对应的请求参数。"""
    defn = INDICATOR_DEFS.get(code)
    if not defn:
        return None
    builder = defn.get("build_params")
    if not builder:
        return None
    return builder(code, ctx)


def parse_indicator_result(code: str, raw_response: Any) -> Any:
    """按注册表的 parse_result 解析（无则原样返回）。"""
    defn = INDICATOR_DEFS.get(code)
    if not defn:
        return raw_response
    parser = defn.get("parse_result")
    if parser:
        return parser(raw_response)
    return raw_response


def parse_indicator_to_standard(code: str, raw_item: Any) -> dict:
    """将指标原始响应解析为统一标准格式 {code, value?, unit?, trend?, error?}。

    优先使用脚本注册的 parse_to_standard；否则走内置逻辑。
    """
    defn = INDICATOR_DEFS.get(code, {})
    script_parser = defn.get("parse_to_standard")
    if script_parser:
        try:
            result = script_parser(code, raw_item)
            if isinstance(result, dict):
                result.setdefault("code", code)
                return result
        except Exception as e:
            logger.warning("script parse_to_standard failed for %s: %s", code, e)
            return {"code": code, "error": f"脚本解析失败: {e}"}
    return _parse_standard_builtin(code, raw_item)


def _parse_standard_builtin(code: str, raw_item: Any) -> dict:
    """内置标准化解析逻辑（与原 MCP 完全一致）。"""
    result = {"code": code}

    if not isinstance(raw_item, dict):
        result["error"] = f"无效响应格式: {raw_item}"
        return result

    data_str = raw_item.get("data")
    if data_str is None:
        result["error"] = "响应中无data字段"
        return result

    if isinstance(data_str, str):
        try:
            parsed = json.loads(data_str)
        except json.JSONDecodeError as e:
            result["error"] = f"data JSON解析失败: {e}"
            return result
    else:
        parsed = data_str

    err_msg = parsed.get("error") if isinstance(parsed, dict) else None
    if err_msg:
        result["error"] = err_msg
        return result
    err_code = parsed.get("errCode") if isinstance(parsed, dict) else None
    err_msg2 = parsed.get("errMsg") if isinstance(parsed, dict) else None
    if err_code is not None and err_code != 0 and err_msg2:
        result["error"] = err_msg2
        return result

    inner_data = parsed.get("data") if isinstance(parsed, dict) else None
    if inner_data is None:
        result["error"] = "响应中无内层data字段"
        return result

    if code == "10029b":
        if not isinstance(inner_data, list) or len(inner_data) == 0:
            result["value"] = 0
            result["unit"] = "个"
            return result
        first = inner_data[0]
        val = first.get("value")
        if val is not None:
            result["value"] = val
        all_val = first.get("all_value")
        if all_val is not None:
            result["trend"] = f"今日累计{all_val}个"
        result["unit"] = "个"

    elif code == "10030":
        if not isinstance(inner_data, list) or len(inner_data) == 0:
            result["value"] = 0
            result["unit"] = "次"
            return result
        total = 0
        for item in inner_data:
            total += item.get("index_val", 0)
        result["value"] = total
        result["unit"] = "次"

    elif code == "10020":
        rows = inner_data.get("rows") if isinstance(inner_data, dict) else None
        if rows and len(rows) > 0:
            val = rows[0].get("value")
            if val is not None:
                result["value"] = val
        result["unit"] = "%"

    elif code == "67851":
        if isinstance(inner_data, (int, float)):
            result["value"] = inner_data
        elif isinstance(inner_data, str) and inner_data.isdigit():
            result["value"] = int(inner_data)
        else:
            result["value"] = 0
        result["unit"] = "天"

    else:
        if not isinstance(inner_data, list) or len(inner_data) == 0:
            result["value"] = 0
            return result
        first = inner_data[0]
        val = first.get("value")
        if val is not None:
            result["value"] = val
        all_val = first.get("all_value")
        if all_val is not None:
            result["trend"] = f"今日累计{all_val}个"
        result["unit"] = "个"

    return result


# ── 区域名称 lookup（area.js）────────────────────────────────────────────

_AREA_LOOKUP: Dict[str, str] = {}


def _load_area_lookup() -> Dict[str, str]:
    """Load orgNo -> value mapping from area.js."""
    if _AREA_LOOKUP:
        return _AREA_LOOKUP

    area_js_path = CONFIG.get("area_js_path") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "area.js"
    )
    try:
        with open(area_js_path, "r", encoding="utf-8") as f:
            content = f.read()
        js = re.sub(r'^export\s+default\s+', '', content.strip())
        js = re.sub(r';?\s*$', '', js)

        def _find_objs(text, start=0):
            objs = []
            i = start
            while i < len(text):
                if text[i] == '{':
                    depth = 1
                    j = i + 1
                    while j < len(text) and depth > 0:
                        if text[j] == '{':
                            depth += 1
                        elif text[j] == '}':
                            depth -= 1
                        elif text[j] in '\'\"':
                            q = text[j]
                            j += 1
                            while j < len(text):
                                if text[j] == '\\':
                                    j += 2
                                    continue
                                if text[j] == q:
                                    break
                                j += 1
                        j += 1
                    objs.append(text[i:j] if depth == 0 else text[i:])
                    i = j
                else:
                    i += 1
            return objs

        def _walk(obj_str):
            pairs = re.findall(r'''([\"']?)(\w+)\1\s*:\s*\"((?:[^\"\\]|\\.)*)\"''', obj_str)
            keys = {k: v for _, k, v in pairs}
            if 'orgNo' in keys and 'value' in keys:
                _AREA_LOOKUP[keys['orgNo']] = keys['value']
            cs = obj_str.find('"children"')
            if cs == -1:
                cs = obj_str.find('children:')
            if cs != -1:
                br = obj_str.find('[', cs)
                if br != -1:
                    for child in _find_objs(obj_str, br + 1):
                        _walk(child)

        top_objs = _find_objs(js)
        if top_objs:
            top = top_objs[0]
            area_pos = top.find('"area"')
            if area_pos == -1:
                area_pos = top.find('area:')
            if area_pos != -1:
                br = top.find('[', area_pos)
                if br != -1:
                    for item in _find_objs(top, br + 1):
                        _walk(item)
    except Exception as e:
        logger.warning("[area lookup] Failed to load area.js: %s", e)

    return _AREA_LOOKUP


def get_area_name(org_no: str) -> str:
    """Look up area name by org_no from area.js."""
    lookup = _load_area_lookup()
    return lookup.get(org_no, "")


# ── 登录上下文缓存 ──────────────────────────────────────────────────────

_LOGIN_CONTEXT_CACHE: Dict[str, dict] = {}


def _get_or_fetch_login_context(login_name: str) -> dict:
    """获取登录上下文（org_no, area_name），带缓存。"""
    if CACHE_LOGIN_CONTEXT:
        cached = _LOGIN_CONTEXT_CACHE.get(login_name)
        if cached:
            logger.info("[cache] Using cached context for %s: org_no=%s", login_name, cached["org_no"])
            return cached

    logger.info("[cache] Fetching context for %s", login_name)
    base_org_id = fetch_base_org_id(login_name)
    org_no = "43101"
    if base_org_id:
        fetched_org_no = fetch_org_no(login_name, base_org_id)
        if fetched_org_no:
            org_no = fetched_org_no

    area_name = get_area_name(org_no)
    ctx = {"org_no": org_no, "area_name": area_name}
    _LOGIN_CONTEXT_CACHE[login_name] = ctx
    return ctx


def clear_login_context_cache(login_name: str = None) -> None:
    """清空登录上下文缓存（login_name 为空则全部清空）。"""
    if login_name:
        _LOGIN_CONTEXT_CACHE.pop(login_name, None)
    else:
        _LOGIN_CONTEXT_CACHE.clear()


def fetch_base_org_id(login_name: str) -> Optional[str]:
    """Step 1: Fetch baseOrgId from user info endpoint."""
    url = f"{API_BASE_URL}/plan/user/queryByLoginName?loginName={login_name}"
    headers = _auth_headers(login_name)
    try:
        data = _http_get(url, headers=headers)
        base_org_id = data.get("data", {}).get("baseorgId")
        if base_org_id:
            logger.info("[Step 1] Fetched baseOrgId: %s", base_org_id)
            return str(base_org_id)
        logger.info("[Step 1] baseorgId not found in response")
        return None
    except Exception as e:
        logger.warning("[Step 1] Failed: %s", e)
        return None


def fetch_org_no(login_name: str, base_org_id: str) -> Optional[str]:
    """Step 2: Fetch org_no from department endpoint."""
    url = (
        f"{API_BASE_URL}/plan/org/queryDeptByLoginName"
        f"?loginName={login_name}"
        f"&baseOrgId={base_org_id}"
        f"&type=app"
    )
    headers = _auth_headers(login_name)
    try:
        data = _http_get(url, headers=headers)
        org_no = data.get("data", {}).get("org_no")
        if org_no:
            logger.info("[Step 2] Fetched org_no: %s", org_no)
            return str(org_no)
        logger.info("[Step 2] org_no not found in response")
        return None
    except Exception as e:
        logger.warning("[Step 2] Failed: %s", e)
        return None


def build_request_context(org_no: str) -> dict:
    """构建请求上下文。"""
    org_lev = _compute_org_lev(org_no)
    final_org_no = _truncate_org_no(org_no)
    return {
        "org_lev": org_lev,
        "org_no": final_org_no,
        "ds": _get_today_ds(),
        "last_month_ym": _get_last_month_ym(),
        "ago_month_ym": _get_ago_month_ym(),
    }


# ── 分组 & 查询 ──────────────────────────────────────────────────────────

def _group_codes_by_url(codes: List[str], ctx: dict) -> Dict[Optional[str], List[Tuple[str, dict]]]:
    """将 codes 按 URL 分组。url=None 表示 /plan/base/counts。"""
    groups: Dict[Optional[str], List[Tuple[str, dict]]] = {}
    for code in codes:
        defn = INDICATOR_DEFS.get(code)
        if not defn:
            continue
        url = defn.get("url")
        params = get_build_params(code, ctx)
        if params is None:
            continue
        groups.setdefault(url, []).append((code, params))
    return groups


def query_indicators_by_codes(login_name: str, org_no: str, codes: List[str]) -> Dict[str, Any]:
    """Step 3: 根据 codes 分组查询指标数据。

    规则:
      - URL 为 None 的 code 合并为一次 POST /plan/base/counts 请求
      - 其他 URL 各自单独请求（POST 或 GET）
    返回 {code: parsed_result, ...}，并追加 area_name。
    """
    ctx = build_request_context(org_no)
    groups = _group_codes_by_url(codes, ctx)
    results: Dict[str, Any] = {}
    headers = _auth_headers(login_name)

    for url, code_params_list in groups.items():
        if url is None:
            batch_payload = [params for code, params in code_params_list]
            target_url = f"{API_BASE_URL}/plan/base/counts"
            logger.info("[Step 3] POST %s with %d indicators (batch)", target_url, len(batch_payload))
            resp = _http_post(target_url, batch_payload, headers=headers)

            if isinstance(resp, dict) and "data" in resp:
                batch_data = resp["data"]
                if isinstance(batch_data, list):
                    for i, (code, _) in enumerate(code_params_list):
                        raw_val = batch_data[i] if i < len(batch_data) else None
                        results[code] = parse_indicator_to_standard(code, raw_val)
                else:
                    for code, _ in code_params_list:
                        results[code] = parse_indicator_to_standard(code, batch_data)
            else:
                for code, _ in code_params_list:
                    results[code] = parse_indicator_to_standard(code, resp)
        else:
            for code, params in code_params_list:
                defn = INDICATOR_DEFS.get(code, {})
                target_url = f"{API_BASE_URL}{url}"
                method = defn.get("method", "POST")
                if method == "GET":
                    query_string = "&".join(f"{k}={v}" for k, v in params.items())
                    full_url = f"{target_url}?{query_string}"
                    logger.info("[Step 3] GET %s for code=%s (single)", full_url, code)
                    resp_raw = _http_get(full_url, headers=headers)
                    resp = {"data": resp_raw}
                else:
                    logger.info("[Step 3] POST %s for code=%s (single)", target_url, code)
                    resp = _http_post(target_url, params, headers=headers)
                results[code] = parse_indicator_to_standard(code, resp)

    area_name = get_area_name(org_no)
    if area_name:
        results["area_name"] = area_name

    return results


def run_query_core_indicators(login_name: str, codes: List[str] = None) -> str:
    """主入口：根据用户名和 codes 数组查询核心指标。

    codes 为 None 时查询所有已注册指标。
    返回 JSON 字符串，按 code 索引。
    """
    login_ctx = _get_or_fetch_login_context(login_name)
    org_no = login_ctx["org_no"]
    area_name = login_ctx["area_name"]

    if codes is None:
        codes = list(INDICATOR_DEFS.keys())
    elif isinstance(codes, str):
        codes = [codes]

    results = query_indicators_by_codes(login_name, org_no, codes)
    if area_name:
        results["area_name"] = area_name
    return json.dumps(results, ensure_ascii=False)


def test_indicator(login_name: str, code: str) -> str:
    """测试指标：返回 code、名字、地区、请求url、方法、参数、原始响应、解析结果。"""
    login_ctx = _get_or_fetch_login_context(login_name)
    org_no = login_ctx["org_no"]
    area_name = login_ctx["area_name"]

    defn = INDICATOR_DEFS.get(code)
    if not defn:
        return json.dumps({"code": code, "error": f"指标 {code} 不存在"}, ensure_ascii=False)

    ctx = build_request_context(org_no)
    params = get_build_params(code, ctx)
    if params is None:
        return json.dumps({"code": code, "error": "无法构建参数"}, ensure_ascii=False)

    headers = _auth_headers(login_name)
    raw_url = defn.get("url")
    if raw_url is None:
        target_url = f"{API_BASE_URL}/plan/base/counts"
        request_url_display = target_url
        method = "POST"
        request_params = params
        resp = _http_post(target_url, [params], headers=headers)
    else:
        target_url = f"{API_BASE_URL}{raw_url}"
        request_url_display = target_url
        method = defn.get("method", "POST")
        request_params = params
        if method == "GET":
            query_string = "&".join(f"{k}={v}" for k, v in params.items())
            full_url = f"{target_url}?{query_string}"
            request_url_display = full_url
            resp_raw = _http_get(full_url, headers=headers)
            resp = {"data": resp_raw}
        else:
            resp = _http_post(target_url, params, headers=headers)

    if raw_url is None:
        raw_data = resp.get("data", [])
        if isinstance(raw_data, list) and len(raw_data) > 0:
            matched = None
            for item in raw_data:
                if isinstance(item, dict) and item.get("code") == code:
                    matched = item
                    break
            if matched is None:
                matched = raw_data[0]
        else:
            matched = raw_data
    else:
        matched = resp

    parsed_result = parse_indicator_to_standard(code, matched)

    result = {
        "code": code,
        "name": defn["name"],
        "area_name": area_name,
        "request_url": request_url_display,
        "request_method": method,
        "request_params": request_params,
        "raw_response": matched,
        "parsed_result": parsed_result,
    }
    return json.dumps(result, ensure_ascii=False)
