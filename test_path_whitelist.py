#!/usr/bin/env python3
"""单元测试：路径白名单校验逻辑（测试 _check_path_whitelist 函数）"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from model_tools import _check_path_whitelist
from hermes_cli.config import load_config


def test_allowed_path():
    """在白名单内的路径应该放行"""
    ok, msg = _check_path_whitelist("read_file", {"path": os.path.expanduser("~")})
    assert ok, f"用户家目录应在白名单内，但被拒绝: {msg}"
    print("PASS: 白名单内路径放行")


def test_blocked_path():
    """在白名单外的路径应被拒绝（仅在 mode != trust 时生效）"""
    config = load_config()
    mode = config.get("security", {}).get("mode", "protection")
    ok, msg = _check_path_whitelist("read_file", {"path": "C:/Windows/win.ini"})
    if mode in ("trust", "off"):
        print(f"INFO: 当前模式为 {mode}，白名单拦截已跳过")
    else:
        assert not ok, f"C:/Windows 不在白名单内，应被拒绝"
        assert "访问被拒绝" in msg
        print("PASS: 白名单外路径被拒绝")


def test_search_files_default():
    """search_files 默认 '.' 跳过"""
    ok, msg = _check_path_whitelist("search_files", {"pattern": "*.txt", "path": "."})
    assert ok, f"search_files 默认 '.' 应放行: {msg}"
    print("PASS: search_files 默认路径 '.' 跳过检查")


def test_non_path_tool():
    """非路径工具放行"""
    ok, msg = _check_path_whitelist("terminal", {"command": "ls"})
    assert ok, f"terminal 等非路径工具应放行: {msg}"
    print("PASS: 非路径工具放行")


def test_vision_url():
    """vision_analyze 的 URL 跳过"""
    ok, msg = _check_path_whitelist("vision_analyze", {"image_url": "https://example.com/img.png"})
    assert ok, f"HTTP URL 应跳过: {msg}"
    print("PASS: vision_analyze HTTP URL 跳过")


def test_no_args():
    """没有路径参数的工具放行"""
    ok, msg = _check_path_whitelist("terminal", {"command": "echo hello"})
    assert ok, f"无路径参数应放行: {msg}"
    print("PASS: 无路径参数工具放行")


if __name__ == "__main__":
    config = load_config()
    mode = config.get("security", {}).get("mode", "unknown")
    paths = config.get("security", {}).get("allowed_paths", [])
    print("=" * 55)
    print(f"当前配置: mode={mode}, allowed_paths={paths}")
    print("=" * 55)
    passed = 0
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                passed += 1
            except AssertionError as e:
                print(f"FAIL: {e}")
                failed += 1
            except Exception as e:
                print(f"ERROR: {name}: {e}")
                failed += 1
    print("=" * 55)
    print(f"结果: {passed} 通过, {failed} 失败")
