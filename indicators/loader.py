"""indicators/loader.py - 脚本指标动态加载

扫描 ~/.hermes/custom_indicators/ind_<code>.py，importlib 按文件路径加载，
把脚本中的约定函数绑定进 engine.INDICATOR_DEFS。

脚本契约（每个脚本可定义以下函数，缺省走默认行为）:
    def build_params(code, ctx) -> dict           # 可选，默认 _build_params_default
    def parse_result(raw_response) -> Any         # 可选，默认原样返回
    def parse_to_standard(code, raw_item) -> dict # 可选，默认内置标准化解析

脚本目录里同时维护 metadata.json:
    [{"code": "...", "name": "...", "url": null, "method": "POST",
      "version": "...", "applied_at": "..."}]
"""
import importlib.util
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Optional

from indicators import engine
from indicators.config import CONFIG

logger = logging.getLogger(__name__)

SCRIPTS_DIR = Path(CONFIG["scripts_dir"])
METADATA_FILE = SCRIPTS_DIR / "metadata.json"
MAX_SCRIPT_BYTES = 64 * 1024  # 64KB 限制

# 已加载脚本模块的强引用（防止 GC）
_loaded_modules: Dict[str, object] = {}


def ensure_scripts_dir() -> None:
    """确保脚本目录存在。"""
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


def script_path(code: str) -> Path:
    return SCRIPTS_DIR / f"ind_{code}.py"


# ── metadata.json 读写 ────────────────────────────────────────────────────

def _read_metadata() -> list:
    try:
        if METADATA_FILE.exists():
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning("read metadata.json failed: %s", e)
    return []


def _write_metadata(items: list) -> None:
    ensure_scripts_dir()
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def get_metadata(code: str) -> Optional[dict]:
    for item in _read_metadata():
        if item.get("code") == code:
            return item
    return None


def upsert_metadata(entry: dict) -> None:
    items = _read_metadata()
    for i, item in enumerate(items):
        if item.get("code") == entry.get("code"):
            items[i] = entry
            break
    else:
        items.append(entry)
    _write_metadata(items)


def remove_metadata(code: str) -> None:
    items = [item for item in _read_metadata() if item.get("code") != code]
    _write_metadata(items)


def list_metadata() -> list:
    return _read_metadata()


# ── 脚本加载 ──────────────────────────────────────────────────────────────

def _compile_check(source: str) -> Optional[str]:
    """语法预检查，返回错误信息（None=通过）。"""
    try:
        compile(source, "<indicator_script>", "exec")
        return None
    except SyntaxError as e:
        return f"脚本语法错误: {e}"


def _load_script_module(code: str) -> Optional[object]:
    """按文件路径加载脚本模块（模块名 ind_<code>，避免冲突）。"""
    path = script_path(code)
    if not path.exists():
        return None
    if path.stat().st_size > MAX_SCRIPT_BYTES:
        logger.warning("script %s exceeds %d bytes, skipped", code, MAX_SCRIPT_BYTES)
        return None

    try:
        mod_name = f"indicator_script_{code}"
        # 清除旧模块，保证热加载
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec is None or spec.loader is None:
            logger.warning("cannot create spec for %s", path)
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        logger.warning("load script %s failed: %s", path, e)
        sys.modules.pop(mod_name, None)
        return None


def _register_script(code: str, mod: object, meta: Optional[dict]) -> bool:
    """把脚本模块的函数绑定进 INDICATOR_DEFS。失败回滚（不注册）。"""
    try:
        defn = {
            "name": (meta or {}).get("name") or getattr(mod, "INDICATOR_NAME", code),
            "url": (meta or {}).get("url") if (meta or {}).get("url") is not None
                   else getattr(mod, "INDICATOR_URL", None),
            "method": (meta or {}).get("method", "POST")
                      if (meta or {}).get("url") is not None
                      else "POST",
            "build_params": getattr(mod, "build_params", engine._build_params_default),
            "parse_result": getattr(mod, "parse_result", None),
            "parse_to_standard": getattr(mod, "parse_to_standard", None),
            "sortOrder": (meta or {}).get("sortOrder", 99),
            "from_script": True,
            "version": (meta or {}).get("version", ""),
        }
        engine.INDICATOR_DEFS[code] = defn
        _loaded_modules[code] = mod
        logger.info("script indicator registered: %s (%s)", code, defn["name"])
        return True
    except Exception as e:
        logger.warning("register script %s failed: %s", code, e)
        engine.INDICATOR_DEFS.pop(code, None)
        return False


def reload_script(code: str) -> dict:
    """热加载单个脚本指标。返回 {ok, message}。"""
    meta = get_metadata(code)
    if not meta:
        return {"ok": False, "message": f"指标 {code} 不在本地应用列表"}
    path = script_path(code)
    if not path.exists():
        return {"ok": False, "message": f"脚本文件不存在: {path}"}

    source = path.read_text(encoding="utf-8")
    err = _compile_check(source)
    if err:
        return {"ok": False, "message": err}

    mod = _load_script_module(code)
    if mod is None:
        return {"ok": False, "message": f"脚本加载失败: {code}"}

    ok = _register_script(code, mod, meta)
    return {"ok": ok, "message": f"指标 {code} 已加载" if ok else f"指标 {code} 注册失败"}


def apply_script(code: str, name: str, script: str, url=None, method="POST",
                 version="1.0", sort_order: int = 99) -> dict:
    """应用脚本指标：写盘 + 元数据 + 热加载。返回 {ok, message}。

    这是 apply 的核心：脚本已经过语法校验，写文件后注册。
    """
    if not code or not script:
        return {"ok": False, "message": "code 和 script 必填"}
    if len(script.encode("utf-8")) > MAX_SCRIPT_BYTES:
        return {"ok": False, "message": f"脚本超过 {MAX_SCRIPT_BYTES} 字节限制"}

    err = _compile_check(script)
    if err:
        return {"ok": False, "message": err}

    ensure_scripts_dir()
    script_path(code).write_text(script, encoding="utf-8")

    entry = {
        "code": code,
        "name": name,
        "url": url,
        "method": method if url else "POST",
        "sortOrder": sort_order,
        "version": version,
    }
    upsert_metadata(entry)

    result = reload_script(code)
    return {"ok": result["ok"], "message": result["message"]}


def unapply_script(code: str) -> dict:
    """取消应用：删除脚本文件 + 元数据 + 注册表条目。返回 {ok, message}。"""
    existed = code in engine.INDICATOR_DEFS or script_path(code).exists()

    path = script_path(code)
    if path.exists():
        try:
            path.unlink()
        except Exception as e:
            return {"ok": False, "message": f"删除脚本文件失败: {e}"}

    remove_metadata(code)
    engine.INDICATOR_DEFS.pop(code, None)
    _loaded_modules.pop(code, None)

    # 清理 sys.modules
    mod_name = f"indicator_script_{code}"
    sys.modules.pop(mod_name, None)

    if not existed:
        return {"ok": True, "message": f"指标 {code} 本来未应用"}
    return {"ok": True, "message": f"指标 {code} 已取消应用"}


def scan_and_load_all() -> Dict[str, dict]:
    """扫描脚本目录，加载所有脚本指标。返回 {code: {"ok", "message"}}。

    网关启动时调用一次；apply/unapply 后调用 reload_all 或 reload_script。
    """
    ensure_scripts_dir()
    results: Dict[str, dict] = {}

    # 先清掉所有 from_script 的旧条目（保持目录为唯一事实源）
    for code in list(engine.INDICATOR_DEFS.keys()):
        if engine.INDICATOR_DEFS[code].get("from_script"):
            engine.INDICATOR_DEFS.pop(code, None)

    for path in sorted(SCRIPTS_DIR.glob("ind_*.py")):
        code = path.stem[len("ind_"):]
        meta = get_metadata(code)
        mod = _load_script_module(code)
        if mod is None:
            results[code] = {"ok": False, "message": "脚本加载失败"}
            continue
        ok = _register_script(code, mod, meta)
        results[code] = {"ok": ok, "message": f"指标 {code} 已加载" if ok else "注册失败"}

    return results


def is_applied(code: str) -> bool:
    """判断指标是否已在本地应用（脚本文件存在）。"""
    return script_path(code).exists()
