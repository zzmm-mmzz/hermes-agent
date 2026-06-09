"""
Shared audit log module for Hermes Gateway.

Provides audit logging functions used by api_server.py, hub_api_server.py,
and model_tools.py (for tool usage tracking).

Events are stored as JSON lines in ~/.hermes/audit_log.json.
"""

import json
import os
import time
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger("audit_log")

# ── 事件类型中文映射 ──────────────────────────────────────────────
# 安全策略类
SECURITY_MODE_CHANGE = "security_mode_change"
SANDBOX_CHANGE = "sandbox_change"
WORKDIR_CHANGE = "workdir_change"
PATH_BLOCKED = "path_blocked"

# Skill 操作类
SKILL_INSTALL = "skill_install"
SKILL_UNINSTALL = "skill_uninstall"
SKILL_UPLOAD = "skill_upload"

# 工具调用类
TOOL_USAGE = "tool_usage"

# 对话记录类
USER_MESSAGE = "user_message"

# 用户登录类
USER_SAVE = "user_save"
USER_LOGOUT = "user_logout"

# 任务管理类
JOB_CREATE = "job_create"
JOB_UPDATE = "job_update"
JOB_DELETE = "job_delete"
JOB_PAUSE = "job_pause"
JOB_RESUME = "job_resume"
JOB_RUN = "job_run"

# 响应管理类
RESPONSE_DELETE = "response_delete"

# 会话管理类
RUN_START = "run_start"
RUN_STOP = "run_stop"
RUN_APPROVAL = "run_approval"

# 审计日志管理类
AUDIT_LOG_CLEAR = "audit_log_clear"

# AI 对话类
CHAT_COMPLETION = "chat_completion"

_TYPE_MAP = {
    SECURITY_MODE_CHANGE: "模式修改",
    SANDBOX_CHANGE: "沙箱切换",
    WORKDIR_CHANGE: "白名单修改",
    PATH_BLOCKED: "路径访问拦截",
    SKILL_INSTALL: "安装技能",
    SKILL_UNINSTALL: "卸载技能",
    SKILL_UPLOAD: "上传技能",
    TOOL_USAGE: "工具调用",
    USER_MESSAGE: "用户提问",
    USER_SAVE: "用户登录",
    USER_LOGOUT: "用户退出",
    JOB_CREATE: "创建任务",
    JOB_UPDATE: "更新任务",
    JOB_DELETE: "删除任务",
    JOB_PAUSE: "暂停任务",
    JOB_RESUME: "恢复任务",
    JOB_RUN: "运行任务",
    RESPONSE_DELETE: "删除响应",
    RUN_START: "启动会话",
    RUN_STOP: "停止会话",
    RUN_APPROVAL: "审批操作",
    AUDIT_LOG_CLEAR: "清空审计日志",
    CHAT_COMPLETION: "对话完成",
}


# ── 路径与 I/O ──────────────────────────────────────────────────


def get_audit_log_path() -> str:
    """Get the audit log file path."""
    config_dir = os.environ.get(
        "HERMES_CONFIG_DIR",
        os.path.join(os.path.expanduser("~"), ".hermes"),
    )
    return os.path.join(config_dir, "audit_log.json")


def read_audit_log() -> list:
    """Read all audit log entries from the JSON lines file."""
    path = get_audit_log_path()
    if not os.path.exists(path):
        return []
    entries = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except (OSError, IOError):
        pass
    return entries


def write_audit_log(entries: list) -> None:
    """Write audit log entries as JSON lines, pruning old entries."""
    path = get_audit_log_path()

    # 延迟导入避免循环依赖
    from hermes_cli.config import load_config_readonly

    cfg = load_config_readonly()
    audit_cfg = cfg.get("audit_log", {})
    max_entries = audit_cfg.get("max_entries", 1000)
    retention_days = audit_cfg.get("retention_days", 30)

    # Prune by retention days
    if retention_days > 0:
        cutoff = time.time() - retention_days * 86400
        entries = [e for e in entries if e.get("timestamp", 0) >= cutoff]

    # Prune by max entries (keep most recent)
    if max_entries > 0 and len(entries) > max_entries:
        entries = entries[-max_entries:]

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except (OSError, IOError):
        pass


# ── 核心记录函数 ────────────────────────────────────────────────


def log_audit_event(
    event_type: str,
    before_value: Any = None,
    after_value: Any = None,
    detail: Optional[dict] = None,
) -> bool:
    """
    Record an audit event.

    Args:
        event_type: 事件类型常量 (e.g. SECURITY_MODE_CHANGE)
        before_value: 变更前的值
        after_value: 变更后的值
        detail: 附加详情字典

    Returns:
        True 表示已写入审计日志，False 表示被禁用
    """
    # 延迟导入避免循环依赖
    from hermes_cli.config import load_config_readonly

    cfg = load_config_readonly()
    audit_cfg = cfg.get("audit_log", {})
    if not audit_cfg.get("enabled", True):
        return False

    operate_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    operate_type = _TYPE_MAP.get(event_type, event_type)

    entry = {
        "operate_time": operate_time,
        "event_type": event_type,
        "operate_type": operate_type,
        "before_value": before_value,
        "after_value": after_value,
        "detail": detail or {},
        "timestamp": time.time(),
    }
    entries = read_audit_log()
    entries.append(entry)
    write_audit_log(entries)
    return True
