"""
Core Indicators MCP Server

一个 MCP (Model Context Protocol) 服务，通过 HTTP/SSE 通信。
提供 query_core_indicators 工具，根据传入的 codes 数组动态组装请求并查询核心指标数据。

依赖: Python 3.9+ 标准库 (无需额外安装包)

运行:
    python server.py
"""

import asyncio
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Tuple
from urllib import request as urllib_request
from urllib.error import URLError
from dataclasses import dataclass, field, asdict

# ── 配置 ──────────────────────────────────────────────────────────────────
# http://25.212.224.159:18080
API_BASE_URL = os.environ.get("API_BASE_URL", "http://22.56.118.69:8086")
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "8100"))

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
    first_of_this_month = now.replace(day=1)
    last_month = first_of_this_month.replace(month=first_of_this_month.month - 1) if first_of_this_month.month > 1 else first_of_this_month.replace(year=first_of_this_month.year - 1, month=12)
    return last_month.strftime("%Y%m")


def _get_ago_month_ym() -> str:
    """Get the same month last year as YYYYMM string."""
    now = datetime.now()
    first_of_this_month = now.replace(day=1)
    if first_of_this_month.month > 1:
        last_month = first_of_this_month.replace(month=first_of_this_month.month - 1)
    else:
        last_month = first_of_this_month.replace(year=first_of_this_month.year - 1, month=12)
    ago = last_month.replace(year=last_month.year - 1)
    return ago.strftime("%Y%m")


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


# ── 本地指标数据文件 ──────────────────────────────────────────────────────

INDICATOR_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "indicators_data.json")


def _load_indicators_data() -> list:
    """从本地文件加载指标数据列表。"""
    if not os.path.exists(INDICATOR_DATA_FILE):
        return []
    try:
        with open(INDICATOR_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except Exception:
        return []


def _save_indicators_data(data: list):
    """保存指标数据列表到本地文件。"""
    with open(INDICATOR_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── url 到 code 的反向映射（用于删除时清理url工具） ─────────────────────

_URL_PLACEHOLDER = None  # None 表示 /plan/base/counts


def _get_url_for_code(code: str) -> Optional[str]:
    """获取指标 code 对应的 url（url工具中的key）。"""
    defn = INDICATOR_DEFS.get(code)
    if not defn:
        return None
    return defn.get("url")


def _get_parse_result_for_code(code: str) -> Optional[callable]:
    """获取指标 code 对应的 parse_result 函数。"""
    defn = INDICATOR_DEFS.get(code)
    if not defn:
        return None
    return defn.get("parse_result")


# ── 指标配置注册表 ────────────────────────────────────────────────────────
# 每个指标定义:
#   code: 指标编码
#   name: 指标名称
#   url: 请求的 API 路径 (None 表示默认 /plan/base/counts)
#   build_params: 根据 context 构建请求参数的函数 (context 包含 org_lev, org_no, ds, ym 等)
#   parse_result: 从响应数据中提取该指标结果的函数


def _build_params_default(code: str, ctx: dict) -> dict:
    """默认参数构建器：通用属性参数。"""
    return {
        "code": code,
        "param": {
            "org_lev": ctx["org_lev"],
            "org_no": ctx["org_no"],
            "pageNum": "1",
            "pageSize": "40",
        },
    }


def _build_params_10030(code: str, ctx: dict) -> dict:
    """当日维修次数：需要 ds 和 idx_no / idx_typ。"""
    return {
        "code": code,
        "param": {
            "org_lev": ctx["org_lev"],
            "org_no": ctx["org_no"],
            "pageNum": "1",
            "pageSize": "10",
            "ds": ctx["ds"],
            "idx_no": "no3",
            "idx_typ": "2",
        },
    }


def _build_params_10013(code: str, ctx: dict) -> dict:
    """当日最大负荷：特定 pageSize=12。"""
    return {
        "code": code,
        "param": {
            "org_lev": ctx["org_lev"],
            "org_no": ctx["org_no"],
            "pageNum": "1",
            "pageSize": "12",
        },
    }


def _build_params_10020(code: str, ctx: dict) -> dict:
    """综合线损率：需要 dt 和 ago_dt。"""
    return {
        "code": code,
        "param": {
            "org_lev": ctx["org_lev"],
            "org_no": ctx["org_no"],
            "dt": ctx["last_month_ym"],
            "ago_dt": ctx["ago_month_ym"],
            "pageNum": "1",
            "pageSize": "40",
        },
    }


def _build_params_67851(code: str, ctx: dict) -> dict:
    """安全运行天数：GET 请求，参数 org_no 作为查询参数。"""
    return {
        "org_no": ctx["org_no"],
    }


def _build_params_common_counts(code: str, ctx: dict) -> dict:
    """通用 count 指标：使用公共参数，code 不同。"""
    return {
        "code": code,
        "param": {
            "org_lev": ctx["org_lev"],
            "org_no": ctx["org_no"],
            "pageNum": "1",
            "pageSize": "40",
        },
    }


# ── 指标定义注册表 ────────────────────────────────────────────────────────

INDICATOR_DEFS: Dict[str, dict] = {
    "10029b": {
        "name": "台区实时停电数",
        "url": None,  # None means /plan/base/counts
        "build_params": _build_params_common_counts,
        "parse_result": None,  # None means return raw response
        "sortOrder": 1,
    },
    "10030": {
        "name": "当日报修次数",
        "url": None,
        "build_params": _build_params_10030,
        "parse_result": None,
        "sortOrder": 2,
    },
    "10020": {
        "name": "综合线损率",
        "url": None,
        "build_params": _build_params_10020,
        "parse_result": None,
        "sortOrder": 3,
    },
    "20016": {
        "name": "低电压用户数",
        "url": None,
        "build_params": _build_params_common_counts,
        "parse_result": None,
        "sortOrder": 4,
    },
    "10012": {
        "name": "实时负荷",
        "url": None,
        "build_params": _build_params_default,
        "parse_result": None,
        "sortOrder": 5,
    },
    # "10013": {
    #     "name": "当日最大负荷",
    #     "url": None,
    #     "build_params": _build_params_10013,
    #     "parse_result": None,
    #     "sortOrder": 6,
    # },
    "67851": {
        "name": "安全运行天数",
        "url": "/plan/safeConfig/selectSafeDayByOrgCode",
        "method": "GET",
        "build_params": _build_params_67851,
        "parse_result": None,
        "sortOrder": 7,
    },
}

# 从本地文件加载自定义指标到注册表
def _load_custom_indicators():
    """从本地文件加载用户自定义指标到注册表。"""
    custom_list = _load_indicators_data()
    for item in custom_list:
        code = item.get("code")
        if not code or code in INDICATOR_DEFS:
            continue
        INDICATOR_DEFS[code] = {
            "name": item.get("name", code),
            "url": item.get("url"),
            "build_params": _build_params_default,
            "parse_result": None,
            "sortOrder": item.get("sortOrder", 99),
        }

_load_custom_indicators()

# ── 关注标记（本地） ───────────────────────────────────────────────────────

INDICATOR_FOLLOWED: Dict[str, bool] = {
    "10029b": True,
    "10030": True,
    "10020": True,
    "20016": True,
    "10012": True,
    # "10013": True,  # 已注释，对应指标已移除
    "67851": True,
}


# ── 工具 1: 根据 code 返回请求参数 ──────────────────────────────────────


def get_build_params(code: str, ctx: dict) -> Optional[dict]:
    """根据 code 返回对应的请求参数。

    Args:
        code: 指标编码
        ctx: 上下文，包含 org_lev, org_no, ds, last_month_ym, ago_month_ym 等

    Returns:
        请求参数字典，若 code 未注册则返回 None
    """
    defn = INDICATOR_DEFS.get(code)
    if not defn:
        return None
    builder = defn.get("build_params")
    if not builder:
        return None
    return builder(code, ctx)


# ── 工具 2: 根据 code 解析响应结果 ──────────────────────────────────────


def parse_indicator_result(code: str, raw_response: Any) -> Any:
    """根据 code 从原始响应中提取该指标的结果。

    如果定义了 parse_result 函数则使用它，否则返回原始响应。

    Args:
        code: 指标编码
        raw_response: 该指标对应的原始响应数据

    Returns:
        解析后的结果
    """
    defn = INDICATOR_DEFS.get(code)
    if not defn:
        return raw_response
    parser = defn.get("parse_result")
    if parser:
        return parser(raw_response)
    return raw_response


# ── 工具 3: 标准化解析指标结果为统一格式 ──────────────────────────────


def parse_indicator_to_standard(code: str, raw_item: Any) -> dict:
    """将指标原始响应解析为统一的标准格式。

    返回值格式: {code, value?, unit?, trend?, error?}
    - 如果响应的 data 字段包含 "error" 字符串，则 error 赋值，无 value/unit/trend
    - 10029b（台区实时停电数）: value=data[0].value, unit="个", trend="今日累计+data[0].all_value+个"
    - 10030（当日报修次数）: value=累加data数组所有index_val, unit="次"
    - 其他指标: 尝试从data[0].value取值, 无说明则返回原数据

    Args:
        code: 指标code
        raw_item: 原始响应条目（字典，包含 "data" 字段）

    Returns:
        标准化后的指标字典
    """
    result = {"code": code}

    # 如果 raw_item 不是 dict，直接返回
    if not isinstance(raw_item, dict):
        result["error"] = f"无效响应格式: {raw_item}"
        return result

    data_str = raw_item.get("data")
    if data_str is None:
        result["error"] = "响应中无data字段"
        return result

    # data 是字符串，尝试解析JSON
    if isinstance(data_str, str):
        try:
            parsed = json.loads(data_str)
        except json.JSONDecodeError as e:
            result["error"] = f"data JSON解析失败: {e}"
            return result
    else:
        parsed = data_str

    # 检查 error
    err_msg = parsed.get("error") if isinstance(parsed, dict) else None
    if err_msg:
        result["error"] = err_msg
        return result
    err_code = parsed.get("errCode") if isinstance(parsed, dict) else None
    err_msg2 = parsed.get("errMsg") if isinstance(parsed, dict) else None
    if err_code is not None and err_code != 0 and err_msg2:
        result["error"] = err_msg2
        return result

    # 获取 data 下的数据
    inner_data = parsed.get("data") if isinstance(parsed, dict) else None
    if inner_data is None:
        result["error"] = "响应中无内层data字段"
        return result

    # 按 code 类型解析
    if code == "10029b":
        # 台区实时停电数：inner_data 是数组，value=data[0].value, unit="个", trend="今日累计+all_value+个"
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
        # 当日报修次数：inner_data 是数组，value=累加所有index_val, unit="次"
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
        # 综合线损率：inner_data 是 dict（rows数组），取 rows[0].value，单位%
        rows = inner_data.get("rows") if isinstance(inner_data, dict) else None
        if rows and len(rows) > 0:
            val = rows[0].get("value")
            if val is not None:
                result["value"] = val
        result["unit"] = "%"
        # 无趋势

    elif code == "67851":
        # 安全运行天数：inner_data 是直接数字，单位是天
        if isinstance(inner_data, (int, float)):
            result["value"] = inner_data
        elif isinstance(inner_data, str) and inner_data.isdigit():
            result["value"] = int(inner_data)
        else:
            result["value"] = 0
        result["unit"] = "天"

    else:
        # 通用：inner_data 是数组时取 data[0].value
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


# ── 关注管理工具 ─────────────────────────────────────────────────────────


def list_all_indicators() -> str:
    """返回所有已注册指标的完整信息（code、name、url、是否关注）。"""
    result = []
    for code, defn in INDICATOR_DEFS.items():
        result.append({
            "code": code,
            "name": defn["name"],
            "url": defn["url"],
            "followed": INDICATOR_FOLLOWED.get(code, False),
        })
    return json.dumps(result, ensure_ascii=False)


def follow_indicator(code: str, followed: bool) -> str:
    """设置指定 code 的指标是否关注。"""
    if code in INDICATOR_DEFS:
        INDICATOR_FOLLOWED[code] = followed
        action = "已关注" if followed else "已取消关注"
        return json.dumps({"success": True, "code": code, "followed": followed, "message": f"{action}指标 {code}"}, ensure_ascii=False)
    return json.dumps({"success": False, "code": code, "message": f"指标 {code} 不存在"}, ensure_ascii=False)


# ── 新增工具: list_indicators（支持list参数） ──────────────────────────

def list_indicators(list_type: Optional[str] = None) -> str:
    """查询指标数据列表。

    Args:
        list_type: 'all'查询所有指标（不受isHide过滤），None只查isHide不为true的指标

    Returns:
        JSON字符串，按sortOrder排序
    """
    items = _load_indicators_data()

    # 用 dict 去重合并：本地文件优先（包含isHide状态），INDICATOR_DEFS 补充
    merged = {}
    for item in items:
        merged[item["code"]] = item
    for code, defn in INDICATOR_DEFS.items():
        if code not in merged:
            merged[code] = {
                "code": code,
                "name": defn["name"],
                "url": defn["url"],
                "isHide": False,
            }
        # 确保每个指标都有 sortOrder
        if "sortOrder" not in merged[code]:
            merged[code]["sortOrder"] = defn.get("sortOrder", 99)
        # 添加 followed 字段
        merged[code]["followed"] = INDICATOR_FOLLOWED.get(code, False)

    # 按 sortOrder 排序
    result = sorted(merged.values(), key=lambda x: x.get("sortOrder", 99))

    # 过滤 isHide（非 all 模式）
    if list_type != 'all':
        result = [item for item in result if not item.get("isHide")]

    return json.dumps(result, ensure_ascii=False)


# ── 新增工具: delete_indicator ──────────────────────────────────────────

def delete_indicator(code: str) -> str:
    """删除指定code的指标。

    删除本地文件中的指标配置、注册表中的定义、关注标记、以及解析逻辑。

    Args:
        code: 指标code

    Returns:
        JSON结果
    """
    if code not in INDICATOR_DEFS:
        return json.dumps({"success": False, "message": f"指标 {code} 不存在"}, ensure_ascii=False)

    # 删除指标定义注册表（INDICATOR_DEFS）
    del INDICATOR_DEFS[code]

    # 删除关注标记（本地）
    INDICATOR_FOLLOWED.pop(code, None)

    # 删除本地文件中的记录（代码工具的指标列表）
    items = _load_indicators_data()
    items = [item for item in items if item.get("code") != code]
    _save_indicators_data(items)

    # 标准化解析结果需要通过重启服务来清除内存中的 INDICATOR_DEFS
    # 删除成功，已注册表中移除此code定义

    return json.dumps({"success": True, "code": code, "message": f"已删除指标 {code}"}, ensure_ascii=False)


# ── 新增工具: hide_indicator ────────────────────────────────────────────

def hide_indicator(code: str, isHide: bool) -> str:
    """设置指标隐藏/显示。

    Args:
        code: 指标code
        isHide: true隐藏 false显示

    Returns:
        JSON结果
    """
    if code not in INDICATOR_DEFS:
        return json.dumps({"success": False, "message": f"指标 {code} 不存在"}, ensure_ascii=False)

    items = _load_indicators_data()
    found = False
    for item in items:
        if item.get("code") == code:
            item["isHide"] = isHide
            found = True
            break

    if not found:
        defn = INDICATOR_DEFS[code]
        items.append({
            "code": code,
            "name": defn["name"],
            "url": defn["url"],
            "isHide": isHide,
            "sortOrder": defn.get("sortOrder", 99),
        })

    _save_indicators_data(items)
    action = "已隐藏" if isHide else "已显示"
    return json.dumps({"success": True, "code": code, "isHide": isHide, "message": f"{action}指标 {code}"}, ensure_ascii=False)


# ── 新增工具: reorder_indicators ────────────────────────────────────────

def reorder_indicators(codes: List[str]) -> str:
    """重排指标顺序。

    Args:
        codes: 排序后的指标code数组

    Returns:
        JSON结果
    """
    items = _load_indicators_data()
    ordered = []
    seen = set()
    for idx, code in enumerate(codes):
        if code in seen:
            continue
        seen.add(code)
        existing = None
        for item in items:
            if item.get("code") == code:
                existing = item
                break
        if existing:
            existing["sortOrder"] = idx + 1
            ordered.append(existing)
        elif code in INDICATOR_DEFS:
            defn = INDICATOR_DEFS[code]
            ordered.append({
                "code": code,
                "name": defn["name"],
                "url": defn["url"],
                "isHide": False,
                "sortOrder": idx + 1,
            })

    next_order = len(codes) + 1
    for item in items:
        if item.get("code") not in seen:
            item["sortOrder"] = next_order
            ordered.append(item)
            seen.add(item.get("code"))
            next_order += 1
    for code, defn in INDICATOR_DEFS.items():
        if code not in seen:
            ordered.append({
                "code": code,
                "name": defn["name"],
                "url": defn["url"],
                "isHide": False,
                "sortOrder": next_order,
            })
            next_order += 1

    _save_indicators_data(ordered)
    return json.dumps({"success": True, "message": "指标顺序已更新"}, ensure_ascii=False)


# ── Area name lookup from area.js ─────────────────────────────────────────

_AREA_LOOKUP: Dict[str, str] = {}


def _load_area_lookup() -> Dict[str, str]:
    """Load orgNo -> value mapping from area.js."""
    if _AREA_LOOKUP:
        return _AREA_LOOKUP

    area_js_path = os.environ.get(
        "AREA_JS_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "area.js"),
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
                        elif text[j] in '\'"':
                            q = text[j]
                            j += 1
                            while j < len(text):
                                if text[j] == '\\':
                                    j += 2; continue
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
            pairs = re.findall(r'''(["']?)(\w+)\1\s*:\s*"((?:[^"\\]|\\.)*)"''', obj_str)
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
        print(f"[area lookup] Failed to load area.js: {e}", file=sys.stderr)

    return _AREA_LOOKUP


def get_area_name(org_no: str) -> str:
    """Look up area name by org_no from area.js."""
    lookup = _load_area_lookup()
    return lookup.get(org_no, "")


# ── 登录上下文缓存（避免重复1、2步） ───────────────────────────────────

_LOGIN_CONTEXT_CACHE: Dict[str, dict] = {}

def _get_or_fetch_login_context(login_name: str) -> dict:
    """获取或获取登录上下文（org_no, area_name）。

    同一login_name在服务启动后只需执行1、2步一次，后续直接使用缓存值。
    """
    cached = _LOGIN_CONTEXT_CACHE.get(login_name)
    if cached:
        print(f"[cache] Using cached context for {login_name}: org_no={cached['org_no']}", file=sys.stderr)
        return cached

    print(f"[cache] Fetching context for {login_name}", file=sys.stderr)
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


# ── 核心查询逻辑 ──────────────────────────────────────────────────────────


def fetch_base_org_id(login_name: str) -> Optional[str]:
    """Step 1: Fetch baseOrgId from user info endpoint."""
    url = f"{API_BASE_URL}/plan/user/queryByLoginName?loginName={login_name}"
    headers = {"login-name": login_name, "Authorization": hashlib.md5(login_name.encode()).hexdigest()}
    try:
        data = _http_get(url, headers=headers)
        base_org_id = data.get("data", {}).get("baseorgId")
        if base_org_id:
            print(f"[Step 1] Fetched baseOrgId: {base_org_id}", file=sys.stderr)
            return str(base_org_id)
        else:
            print(f"[Step 1] baseorgId not found in response", file=sys.stderr)
            return None
    except Exception as e:
        print(f"[Step 1] Failed: {e}", file=sys.stderr)
        return None


def fetch_org_no(login_name: str, base_org_id: str) -> Optional[str]:
    """Step 2: Fetch org_no from department endpoint."""
    url = (
        f"{API_BASE_URL}/plan/org/queryDeptByLoginName"
        f"?loginName={login_name}"
        f"&baseOrgId={base_org_id}"
        f"&type=app"
    )
    headers = {"login-name": login_name, "Authorization": hashlib.md5(login_name.encode()).hexdigest()}
    try:
        data = _http_get(url, headers=headers)
        org_no = data.get("data", {}).get("org_no")
        if org_no:
            print(f"[Step 2] Fetched org_no: {org_no}", file=sys.stderr)
            return str(org_no)
        else:
            print(f"[Step 2] org_no not found in response", file=sys.stderr)
            return None
    except Exception as e:
        print(f"[Step 2] Failed: {e}", file=sys.stderr)
        return None


def _group_codes_by_url(codes: List[str], ctx: dict) -> Dict[Optional[str], List[Tuple[str, dict]]]:
    """将 codes 按 URL 分组。

    相同 URL 的 code 可以合并到同一个请求中。
    url=None 表示 /plan/base/counts。

    Returns:
        {url: [(code, request_params), ...]}
    """
    groups: Dict[Optional[str], List[Tuple[str, dict]]] = {}
    for code in codes:
        defn = INDICATOR_DEFS.get(code)
        if not defn:
            continue
        url = defn.get("url")  # None means /plan/base/counts
        params = get_build_params(code, ctx)
        if params is None:
            continue
        groups.setdefault(url, []).append((code, params))
    return groups


def query_indicators_by_codes(login_name: str, org_no: str, codes: List[str]) -> Dict[str, Any]:
    """Step 3: 根据传入的 codes 数组，分组查询指标数据。

    规则:
      - URL 为 None（即 /plan/base/counts）的 code 合并为一次 POST 请求，
        code参数拼接在一起
      - 其他 URL 各自单独请求
    最后将所有结果按 code 组装返回。

    Args:
        login_name: 登录用户名
        org_no: 组织机构编码
        codes: 要查询的指标 code 数组

    Returns:
        {code: parsed_result, ...} 按 code 索引的结果字典
    """
    org_lev = _compute_org_lev(org_no)
    final_org_no = _truncate_org_no(org_no)
    today = _get_today_ds()
    last_month = _get_last_month_ym()
    ago_month = _get_ago_month_ym()

    ctx = {
        "org_lev": org_lev,
        "org_no": final_org_no,
        "ds": today,
        "last_month_ym": last_month,
        "ago_month_ym": ago_month,
    }

    # 按 URL 分组
    groups = _group_codes_by_url(codes, ctx)

    results: Dict[str, Any] = {}
    headers = {
        "login-name": login_name,
        "Content-Type": "application/json",
        "Authorization": hashlib.md5(login_name.encode()).hexdigest(),
    }

    for url, code_params_list in groups.items():
        if url is None:
            # /plan/base/counts: code参数拼接一起，用的一个请求
            batch_payload = [params for code, params in code_params_list]
            target_url = f"{API_BASE_URL}/plan/base/counts"
            print(f"[Step 3] POST {target_url} with {len(batch_payload)} indicators (batch)", file=sys.stderr)
            resp = _http_post(target_url, batch_payload, headers=headers)

            # 从 batch 响应中为每个 code 提取结果
            if isinstance(resp, dict) and "data" in resp:
                batch_data = resp["data"]
                # 如果返回的是数组，按顺序匹配 code
                if isinstance(batch_data, list):
                    for i, (code, _) in enumerate(code_params_list):
                        if i < len(batch_data):
                            raw_val = batch_data[i]
                        else:
                            raw_val = None
                        results[code] = parse_indicator_to_standard(code, raw_val)
                else:
                    # 非数组响应，全部 code 共用同一个响应
                    for code, _ in code_params_list:
                        results[code] = parse_indicator_to_standard(code, batch_data)
            else:
                for code, _ in code_params_list:
                    results[code] = parse_indicator_to_standard(code, resp)
        else:
            # 其他 URL: 单独请求
            for code, params in code_params_list:
                defn = INDICATOR_DEFS.get(code, {})
                target_url = f"{API_BASE_URL}{url}"
                method = defn.get("method", "POST")
                if method == "GET":
                    # GET 请求：将 params 作为查询参数拼接到 URL
                    query_string = "&".join(f"{k}={v}" for k, v in params.items())
                    full_url = f"{target_url}?{query_string}"
                    print(f"[Step 3] GET {full_url} for code={code} (single)", file=sys.stderr)
                    resp_raw = _http_get(full_url, headers=headers)
                    # _http_get 返回完整 JSON，包装成带 data 的 dict
                    resp = {"data": resp_raw}
                else:
                    print(f"[Step 3] POST {target_url} for code={code} (single)", file=sys.stderr)
                    resp = _http_post(target_url, params, headers=headers)
                results[code] = parse_indicator_to_standard(code, resp)

    # 追加区域名称
    area_name = get_area_name(org_no)
    if area_name:
        results["area_name"] = area_name

    return results


# ── 新增工具: test_indicator ──────────────────────────────────────────────


def build_request_context(org_no: str) -> dict:
    """构建请求上下文。"""
    org_lev = _compute_org_lev(org_no)
    final_org_no = _truncate_org_no(org_no)
    today = _get_today_ds()
    last_month = _get_last_month_ym()
    ago_month = _get_ago_month_ym()

    return {
        "org_lev": org_lev,
        "org_no": final_org_no,
        "ds": today,
        "last_month_ym": last_month,
        "ago_month_ym": ago_month,
    }


def test_indicator(login_name: str, code: str) -> str:
    """测试指标。

    第1、2步与query_core_indicators一致（获取baseOrgId、org_no）。
    第3步返回指标的详细信息：code、名字、地区、原请求的url、请求方式、原请求参数、原返回值、处理后的返回值。

    Args:
        login_name: 登录名
        code: 指标code

    Returns:
        JSON字符串包含测试结果
    """
    print(f"[test_indicator] Testing code={code} for user={login_name}", file=sys.stderr)

    # Step 1 & 2: 获取或从缓存读取登录上下文
    login_ctx = _get_or_fetch_login_context(login_name)
    org_no = login_ctx["org_no"]
    area_name = login_ctx["area_name"]

    # Step 3: 构建请求并执行
    defn = INDICATOR_DEFS.get(code)
    if not defn:
        return json.dumps({
            "code": code,
            "error": f"指标 {code} 不存在",
        }, ensure_ascii=False)

    ctx = build_request_context(org_no)
    params = get_build_params(code, ctx)

    if params is None:
        return json.dumps({
            "code": code,
            "error": f"无法构建参数",
        }, ensure_ascii=False)

    # 确定 url
    raw_url = defn.get("url")
    if raw_url is None:
        target_url = f"{API_BASE_URL}/plan/base/counts"
        # /plan/base/counts 是批量请求
        request_url_display = f"{API_BASE_URL}/plan/base/counts"
        method = "POST"
        request_params = params
        resp = _http_post(target_url, [params], headers={
            "login-name": login_name,
            "Content-Type": "application/json",
            "Authorization": hashlib.md5(login_name.encode()).hexdigest(),
        })
    else:
        target_url = f"{API_BASE_URL}{raw_url}"
        request_url_display = target_url
        method = defn.get("method", "POST")
        request_params = params
        if method == "GET":
            query_string = "&".join(f"{k}={v}" for k, v in params.items())
            full_url = f"{target_url}?{query_string}"
            request_url_display = full_url
            resp_raw = _http_get(full_url, headers={
                "login-name": login_name,
                "Authorization": hashlib.md5(login_name.encode()).hexdigest(),
            })
            resp = {"data": resp_raw}
        else:
            resp = _http_post(target_url, params, headers={
                "login-name": login_name,
                "Content-Type": "application/json",
                "Authorization": hashlib.md5(login_name.encode()).hexdigest(),
            })

    # 解析返回值 - 使用统一的 parse_indicator_to_standard
    if raw_url is None:
        # /plan/base/counts 返回 batch 响应，data 是数组
        raw_data = resp.get("data", [])
        if isinstance(raw_data, list) and len(raw_data) > 0:
            # 找到对应code的条目
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
        # 单独请求，resp 整体就是响应
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


# ── MCP Tool 入口 ─────────────────────────────────────────────────────────


def run_query_core_indicators(login_name: str, codes: List[str] = None) -> str:
    """
    主入口：根据用户名和 codes 数组查询核心指标。

    1. 获取 baseOrgId
    2. 获取 org_no
    3. 根据 codes 分组查询并组装结果
       - url 是 None（/plan/base/counts）: code参数拼接一起，一个请求
       - 其他 url: 单独请求

    Args:
        login_name: 登录用户名
        codes: 要查询的指标 code 列表。为 None 时查询所有被关注的指标。

    Returns:
        JSON 字符串，按 code 索引的结果。
    """
    print(f"[query_core_indicators] Starting for user: {login_name}, codes: {codes}", file=sys.stderr)

    # Step 1 & 2: 获取或从缓存读取登录上下文
    login_ctx = _get_or_fetch_login_context(login_name)
    org_no = login_ctx["org_no"]
    area_name = login_ctx["area_name"]

    print(f"[query_core_indicators] Using org_no: {org_no}", file=sys.stderr)

    if codes is None:
        codes = [code for code, followed in INDICATOR_FOLLOWED.items() if followed]

    result = query_indicators_by_codes(login_name, org_no, codes)

    # 将结果包装为 indicators 数组格式
    indicators_list = []
    for code in codes:
        if code in result:
            item = result[code]
            indicators_list.append(item)
        else:
            indicators_list.append({"code": code, "error": "未找到指标数据"})

    output = {"indicators": indicators_list}
    if area_name:
        output["area_name"] = area_name

    return json.dumps(output, ensure_ascii=False)


# ── MCP Protocol (HTTP/SSE Transport) ────────────────────────────────────

RECEIVED_REQUESTS: Dict[str, Any] = {}


def _make_jsonrpc_response(req_id: Any, result: Any = None, error: Any = None) -> str:
    """Build a JSON-RPC response string."""
    resp = {"jsonrpc": "2.0", "id": req_id}
    if error is not None:
        resp["error"] = error
    else:
        resp["result"] = result
    return json.dumps(resp, ensure_ascii=False)


def _make_jsonrpc_request(method: str, params: Any = None, req_id: Any = None) -> str:
    """Build a JSON-RPC request string."""
    if req_id is None:
        req_id = str(int(time.time() * 1000))
    req = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        req["params"] = params
    return json.dumps(req, ensure_ascii=False), req_id


# ── SSE Server ───────────────────────────────────────────────────────────


async def handle_sse_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handle a single SSE client connection (MCP session)."""
    client_addr = writer.get_extra_info("peername", ("unknown", 0))
    print(f"[SSE] Client connected: {client_addr}", file=sys.stderr)

    # Send SSE headers with CORS
    sse_headers = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: text/event-stream\r\n"
        "Cache-Control: no-cache\r\n"
        "Connection: keep-alive\r\n"
        "Access-Control-Allow-Origin: *\r\n"
        "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
        "Access-Control-Allow-Headers: Content-Type, Authorization, login-name\r\n"
        "Access-Control-Max-Age: 86400\r\n"
        "\r\n"
    )
    writer.write(sse_headers.encode("utf-8"))
    await writer.drain()

    # Send endpoint event
    endpoint_msg = f"event: endpoint\ndata: /messages/?session_id={client_addr[1]}\n\n"
    writer.write(endpoint_msg.encode("utf-8"))
    await writer.drain()

    # Keep SSE connection alive, read incoming messages
    buffer = ""
    try:
        while True:
            data = await asyncio.wait_for(reader.read(4096), timeout=None)
            if not data:
                break
            buffer += data.decode("utf-8")

            # Process complete lines
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if line.startswith("data: "):
                    payload = line[6:]
                    print(f"[SSE] Received: {payload[:200]}", file=sys.stderr)
                    try:
                        msg = json.loads(payload)
                        response = handle_mcp_message(msg)
                        if response:
                            sse_data = f"data: {response}\n\n"
                            writer.write(sse_data.encode("utf-8"))
                            await writer.drain()
                    except json.JSONDecodeError:
                        pass
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"[SSE] Error: {e}", file=sys.stderr)
    finally:
        print(f"[SSE] Client disconnected: {client_addr}", file=sys.stderr)
        writer.close()


def handle_mcp_message(msg: dict) -> Optional[str]:
    """Process an MCP JSON-RPC message and return a response string."""
    req_id = msg.get("id")
    method = msg.get("method", "")
    params = msg.get("params", {})

    if method == "initialize":
        return _make_jsonrpc_response(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "core-indicators",
                "version": "2.0.0",
            }
        })

    elif method == "notifications/initialized":
        return None

    elif method == "tools/list":
        return _make_jsonrpc_response(req_id, {
            "tools": [
                {
                    "name": "query_core_indicators",
                    "description": "查询核心指标数据。根据传入的用户名和指标 code 数组，自动获取组织机构信息并查询指定的核心指标。codes 为空时默认查询所有已关注的指标。",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "login_name": {
                                "type": "string",
                                "description": "当前登录用户名",
                            },
                            "codes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "要查询的指标 code 数组，例如 ['10030', '10020']。为空或 null 时默认查询所有已关注的指标。",
                            },
                        },
                        "required": ["login_name"],
                    },
                },
                {
                    "name": "list_indicators",
                    "description": "查询本地文件的指标数据列表。带 list='all' 查询所有指标（包含已隐藏的），无参数时只返回 isHide 不为 true 的指标。",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "list": {
                                "type": "string",
                                "description": "传 'all' 查询所有指标（包括已隐藏的），不传或 null 只查询未隐藏的指标",
                            },
                        },
                    },
                },
                {
                    "name": "follow_indicator",
                    "description": "关注/取消关注指标。followed=true 关注，followed=false 取消关注。",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "指标 code",
                            },
                            "followed": {
                                "type": "boolean",
                                "description": "true 关注，false 取消关注",
                            },
                        },
                        "required": ["code", "followed"],
                    },
                },
                {
                    "name": "delete_indicator",
                    "description": "删除指标。删除本地文件中的指标配置以及注册表中的定义。",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "指标 code",
                            },
                        },
                        "required": ["code"],
                    },
                },
                {
                    "name": "hide_indicator",
                    "description": "设置指标隐藏/显示。isHide=true 隐藏，isHide=false 显示。",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "指标 code",
                            },
                            "isHide": {
                                "type": "boolean",
                                "description": "true 隐藏，false 显示",
                            },
                        },
                        "required": ["code", "isHide"],
                    },
                },
                {
                    "name": "reorder_indicators",
                    "description": "重排指标顺序。传入排序后的指标 code 数组。",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "codes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "排序后的指标 code 数组",
                            },
                        },
                        "required": ["codes"],
                    },
                },
                {
                    "name": "test_indicator",
                    "description": "测试单个指标。第1、2步与query_core_indicators一致，第3步返回指标的完整测试信息：code、名字、地区、原请求url、请求方式、原请求参数、原返回值、处理后的返回值。",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "login_name": {
                                "type": "string",
                                "description": "登录名",
                            },
                            "code": {
                                "type": "string",
                                "description": "指标 code",
                            },
                        },
                        "required": ["login_name", "code"],
                    },
                },
            ]
        })

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name == "query_core_indicators":
            login_name = arguments.get("login_name", "")
            if not login_name:
                return _make_jsonrpc_response(req_id, error={
                    "code": -32000,
                    "message": "login_name is required",
                })
            codes = arguments.get("codes", None)
            result_text = run_query_core_indicators(login_name, codes)
            return _make_jsonrpc_response(req_id, {
                "content": [{"type": "text", "text": result_text}]
            })

        elif tool_name == "list_indicators":
            list_type = arguments.get("list", None)
            result_text = list_indicators(list_type)
            return _make_jsonrpc_response(req_id, {
                "content": [{"type": "text", "text": result_text}]
            })

        elif tool_name == "follow_indicator":
            code = arguments.get("code", "")
            followed = arguments.get("followed")
            if not code or followed is None:
                return _make_jsonrpc_response(req_id, error={
                    "code": -32000,
                    "message": "code and followed are required",
                })
            result_text = follow_indicator(code, followed)
            return _make_jsonrpc_response(req_id, {
                "content": [{"type": "text", "text": result_text}]
            })

        elif tool_name == "delete_indicator":
            code = arguments.get("code", "")
            if not code:
                return _make_jsonrpc_response(req_id, error={
                    "code": -32000,
                    "message": "code is required",
                })
            result_text = delete_indicator(code)
            return _make_jsonrpc_response(req_id, {
                "content": [{"type": "text", "text": result_text}]
            })

        elif tool_name == "hide_indicator":
            code = arguments.get("code", "")
            isHide = arguments.get("isHide", arguments.get("is_hide"))
            if not code or isHide is None:
                return _make_jsonrpc_response(req_id, error={
                    "code": -32000,
                    "message": "code and isHide are required",
                })
            result_text = hide_indicator(code, isHide)
            return _make_jsonrpc_response(req_id, {
                "content": [{"type": "text", "text": result_text}]
            })

        elif tool_name == "reorder_indicators":
            codes = arguments.get("codes")
            if not codes or not isinstance(codes, list):
                return _make_jsonrpc_response(req_id, error={
                    "code": -32000,
                    "message": "codes array is required",
                })
            result_text = reorder_indicators(codes)
            return _make_jsonrpc_response(req_id, {
                "content": [{"type": "text", "text": result_text}]
            })

        elif tool_name == "test_indicator":
            login_name = arguments.get("login_name", "")
            code = arguments.get("code", "")
            if not login_name or not code:
                return _make_jsonrpc_response(req_id, error={
                    "code": -32000,
                    "message": "login_name and code are required",
                })
            result_text = test_indicator(login_name, code)
            return _make_jsonrpc_response(req_id, {
                "content": [{"type": "text", "text": result_text}]
            })

        else:
            return _make_jsonrpc_response(req_id, error={
                "code": -32601,
                "message": f"Unknown tool: {tool_name}",
            })

    elif method == "ping":
        return _make_jsonrpc_response(req_id, {})

    else:
        return _make_jsonrpc_response(req_id, error={
            "code": -32601,
            "message": f"Method not found: {method}",
        })


# ── HTTP POST handler for /messages/ ──────────────────────────────────────


async def handle_messages(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handle incoming POST messages for MCP."""
    data = await reader.read(65536)
    if not data:
        writer.close()
        return

    raw = data.decode("utf-8")
    print(f"[Messages] Received POST data: {raw[:300]}", file=sys.stderr)

    # Parse HTTP POST
    response_body = b""
    try:
        if "\r\n\r\n" in raw:
            _, body = raw.split("\r\n\r\n", 1)
        else:
            body = raw

        msg = json.loads(body.strip())
        resp_text = handle_mcp_message(msg)
        if resp_text:
            response_body = resp_text.encode("utf-8")
    except Exception as e:
        print(f"[Messages] Error: {e}", file=sys.stderr)
        response_body = json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": f"Parse error: {e}"},
        }).encode("utf-8")

    http_response = (
        f"HTTP/1.1 200 OK\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(response_body)}\r\n"
        f"Access-Control-Allow-Origin: *\r\n"
        f"\r\n"
    ).encode("utf-8") + response_body

    writer.write(http_response)
    await writer.drain()
    writer.close()


# ── HTTP endpoints for direct REST usage ──────────────────────────────────


async def handle_http(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """HTTP router for SSE, messages, and direct tool call."""
    try:
        data = await asyncio.wait_for(reader.read(65536), timeout=10)
    except asyncio.TimeoutError:
        writer.close()
        return

    if not data:
        writer.close()
        return

    raw = data.decode("utf-8", errors="replace")
    first_line = raw.split("\r\n")[0] if "\r\n" in raw else raw.split("\n")[0]

    method = first_line.split(" ")[0] if " " in first_line else "GET"
    path = first_line.split(" ")[1] if len(first_line.split(" ")) > 1 else "/"

    # Handle CORS preflight
    if method == "OPTIONS":
        resp = (
            "HTTP/1.1 204 No Content\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
            "Access-Control-Allow-Headers: Content-Type, Authorization, login-name\r\n"
            "Access-Control-Max-Age: 86400\r\n"
            "\r\n"
        ).encode("utf-8")
        writer.write(resp)
        await writer.drain()
        writer.close()
        return

    if path == "/sse":
        await handle_sse_client(reader, writer)
    elif path.startswith("/messages/"):
        await handle_messages(reader, writer)
    elif path == "/tools/indicators" and method == "POST":
        await handle_direct_tool_call(raw, writer)
    else:
        body = json.dumps({
            "server": "core-indicators MCP Server v2",
            "endpoints": {
                "sse": "/sse (GET) - SSE connection for MCP",
                "messages": "/messages/ (POST) - MCP message endpoint",
                "tools/indicators": "/tools/indicators (POST) - Direct tool call",
            }
        }).encode("utf-8")
        resp = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Access-Control-Allow-Origin: *\r\n"
            f"\r\n"
        ).encode("utf-8") + body
        writer.write(resp)
        await writer.drain()
        writer.close()


async def handle_direct_tool_call(raw: str, writer: asyncio.StreamWriter):
    """Handle direct POST /tools/indicators with JSON-RPC style body."""
    try:
        if "\r\n\r\n" in raw:
            _, body = raw.split("\r\n\r\n", 1)
        else:
            body = raw
        params = json.loads(body.strip())
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name == "query_core_indicators":
            login_name = arguments.get("login_name", "")
            if not login_name:
                result = json.dumps({"error": "login_name is required"})
            else:
                codes = arguments.get("codes", None)
                result = run_query_core_indicators(login_name, codes)
        elif tool_name == "list_indicators":
            list_type = arguments.get("list", None)
            result = list_indicators(list_type)
        elif tool_name == "follow_indicator":
            code = arguments.get("code", "")
            followed = arguments.get("followed")
            if not code or followed is None:
                result = json.dumps({"error": "code and followed are required"})
            else:
                result = follow_indicator(code, followed)
        elif tool_name == "delete_indicator":
            code = arguments.get("code", "")
            if not code:
                result = json.dumps({"error": "code is required"})
            else:
                result = delete_indicator(code)
        elif tool_name == "hide_indicator":
            code = arguments.get("code", "")
            isHide = arguments.get("isHide", arguments.get("is_hide"))
            if not code or isHide is None:
                result = json.dumps({"error": "code and isHide are required"})
            else:
                result = hide_indicator(code, isHide)
        elif tool_name == "reorder_indicators":
            codes = arguments.get("codes")
            if not codes or not isinstance(codes, list):
                result = json.dumps({"error": "codes array is required"})
            else:
                result = reorder_indicators(codes)
        elif tool_name == "test_indicator":
            login_name = arguments.get("login_name", "")
            code = arguments.get("code", "")
            if not login_name or not code:
                result = json.dumps({"error": "login_name and code are required"})
            else:
                result = test_indicator(login_name, code)
        else:
            result = json.dumps({"error": f"Unknown tool: {tool_name}"})

        response_body = result.encode("utf-8")
        http_response = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(response_body)}\r\n"
            f"Access-Control-Allow-Origin: *\r\n"
            f"\r\n"
        ).encode("utf-8") + response_body

        writer.write(http_response)
        await writer.drain()
    except Exception as e:
        err_body = json.dumps({"error": str(e)}).encode("utf-8")
        resp = (
            f"HTTP/1.1 400 Bad Request\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(err_body)}\r\n"
            f"\r\n"
        ).encode("utf-8") + err_body
        writer.write(resp)
        await writer.drain()
    finally:
        writer.close()


# ── Main ──────────────────────────────────────────────────────────────────


async def main():
    server = await asyncio.start_server(handle_http, MCP_HOST, MCP_PORT)
    addr = server.sockets[0].getsockname()
    print(f"MCP Core Indicators Server v2 running on http://{addr[0]}:{addr[1]}", file=sys.stderr)
    print("", file=sys.stderr)
    print("Endpoints:", file=sys.stderr)
    print("  SSE (MCP):   GET  /sse", file=sys.stderr)
    print("  Messages:    POST /messages/", file=sys.stderr)
    print("  Direct call: POST /tools/indicators", file=sys.stderr)
    print("", file=sys.stderr)
    print("Example direct call:", file=sys.stderr)
    print('  curl -X POST http://localhost:8100/tools/indicators \\', file=sys.stderr)
    print('    -H "Content-Type: application/json" \\', file=sys.stderr)
    print('    -d \'{"name": "query_core_indicators", "arguments": {"login_name": "testuser", "codes": ["10030", "10020"]}}\'', file=sys.stderr)
    print("", file=sys.stderr)

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
