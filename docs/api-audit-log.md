# 审计日志 API

查询和清空 Hermes Agent 的审计日志。所有操作（安全策略、Skill 管理、任务管理、用户登录、对话、工具调用等）都会自动记录。

## 通用响应格式

所有审计条目统一使用以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `time` | string | 操作时间，格式 `YYYY-MM-DD HH:mm:ss` |
| `action` | string | 操作描述（中文，如"模式修改"、"工具调用"） |
| `type` | string | 事件类型码（英文，如 `security_mode_change`） |
| `detail` | object | 详情，不同事件类型的字段不同（见下方各类型说明） |

分页外层字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `total` | int | 总条数 |
| `offset` | int | 当前偏移 |
| `limit` | int | 每页条数 |
| `entries` | array | 审计条目列表 |

---

## GET /api/audit/log

获取审计日志条目。

### 查询参数

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `type` | string | 可选 | 按事件类型码过滤 |
| `since` | string | 可选 | ISO 时间戳，包含此时间之后的条目 |
| `until` | string | 可选 | ISO 时间戳，包含此时间之前的条目 |
| `offset` | int | 0 | 分页偏移 |
| `limit` | int | 20 | 每页条数（最大 200） |

---

## 事件类型与 detail 字段说明

### 1. 安全策略类

#### `security_mode_change` — 安全模式切换

| detail 字段 | 类型 | 说明 |
|------------|------|------|
| `before` | string | 切换前模式（如 `trust`） |
| `after` | string | 切换后模式（如 `strict`） |
| `mode` | string | 新模式 |
| `previous_mode` | string | 旧模式 |

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "模式修改",
  "type": "security_mode_change",
  "detail": {
    "before": "trust",
    "after": "strict",
    "mode": "strict",
    "previous_mode": "trust"
  }
}
```

#### `sandbox_change` — 沙箱环境切换

| detail 字段 | 类型 | 说明 |
|------------|------|------|
| `before` | string | 切换前后端（如 `local`） |
| `after` | string | 切换后后端（如 `docker`） |
| `backend` | string | 新后端 |
| `sandbox_enabled` | bool | 沙箱是否启用 |

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "沙箱切换",
  "type": "sandbox_change",
  "detail": {
    "before": "local",
    "after": "docker",
    "backend": "docker",
    "sandbox_enabled": true
  }
}
```

#### `workdir_change` — 路径白名单变更

| detail 字段 | 类型 | 说明 |
|------------|------|------|
| `before` | array | 修改前的白名单路径列表 |
| `after` | array | 修改后的白名单路径列表 |
| `allowed_paths` | array | 当前白名单路径列表 |

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "白名单修改",
  "type": "workdir_change",
  "detail": {
    "before": ["~"],
    "after": ["~", "/data/project"],
    "allowed_paths": ["~", "/data/project"]
  }
}
```

---

### 2. Skill 管理类

#### `skill_install` — 安装技能

| detail 字段 | 类型 | 说明 |
|------------|------|------|
| `after` | string | 安装的 skill slug |
| `slug` | string | Skill 标识 |
| `version` | string/null | 安装版本（不指定时为 null） |

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "安装技能",
  "type": "skill_install",
  "detail": {
    "after": "my-skill",
    "slug": "my-skill",
    "version": "1.0.0"
  }
}
```

#### `skill_uninstall` — 卸载技能

| detail 字段 | 类型 | 说明 |
|------------|------|------|
| `before` | string | 卸载的 skill slug |
| `slug` | string | Skill 标识 |

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "卸载技能",
  "type": "skill_uninstall",
  "detail": {
    "before": "my-skill",
    "slug": "my-skill"
  }
}
```

#### `skill_upload` — 上传技能

| detail 字段 | 类型 | 说明 |
|------------|------|------|
| `file_name` | string | 上传的文件名 |
| `result` | string | 上传结果消息 |

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "上传技能",
  "type": "skill_upload",
  "detail": {
    "file_name": "my-skill.zip",
    "result": "Skill published successfully"
  }
}
```

---

### 3. 工具调用类

#### `tool_usage` — Agent 工具调用

| detail 字段 | 类型 | 说明 |
|------------|------|------|
| `tool_name` | string | 工具名（如 `web_search`、`execute_code`） |
| `task_id` | string | 任务/会话 ID |
| `duration_ms` | int | 工具执行耗时（毫秒） |
| `is_error` | bool | 是否执行出错 |
| `error` | string | 出错时的错误信息（仅出错时有此字段） |

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "工具调用",
  "type": "tool_usage",
  "detail": {
    "tool_name": "web_search",
    "task_id": "run_abc123",
    "duration_ms": 1234,
    "is_error": false
  }
}
```

出错时：
```json
{
  "time": "2026-06-09 10:00:00",
  "action": "工具调用",
  "type": "tool_usage",
  "detail": {
    "tool_name": "web_search",
    "task_id": "run_abc123",
    "error": "Error executing web_search: Connection timeout"
  }
}
```

---

### 4. 对话记录类

#### `user_message` — 用户提问

每次用户与 AI 对话时记录。

| detail 字段 | 类型 | 说明 |
|------------|------|------|
| `question` | string | 用户提问内容（截取前 500 字） |
| `answer_preview` | string | AI 回答预览（截取前 200 字） |
| `session_id` | string | 会话 ID |

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "用户提问",
  "type": "user_message",
  "detail": {
    "question": "帮我查一下昨天的销售数据",
    "answer_preview": "好的，我来查询昨天的销售数据...",
    "session_id": "abc123def456"
  }
}
```

---

### 5. 用户登录类

#### `user_save` — 保存用户信息/登录

| detail 字段 | 类型 | 说明 |
|------------|------|------|
| `user_fields` | array | 保存的用户信息字段名列表 |

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "用户登录",
  "type": "user_save",
  "detail": {
    "user_fields": ["username", "token", "department"]
  }
}
```

#### `user_logout` — 用户退出登录

无 detail 字段。

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "用户退出",
  "type": "user_logout",
  "detail": {}
}
```

---

### 6. 任务管理类

#### `job_create` — 创建定时任务

| detail 字段 | 类型 | 说明 |
|------------|------|------|
| `job_name` | string | 任务名称 |
| `schedule` | string | 调度表达式 |

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "创建任务",
  "type": "job_create",
  "detail": {
    "job_name": "每日数据同步",
    "schedule": "0 9 * * *"
  }
}
```

#### `job_update` — 更新定时任务

| detail 字段 | 类型 | 说明 |
|------------|------|------|
| `job_id` | string | 任务 ID |
| `updated_fields` | array | 更新的字段名列表 |

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "更新任务",
  "type": "job_update",
  "detail": {
    "job_id": "a1b2c3d4e5f6",
    "updated_fields": ["schedule", "prompt"]
  }
}
```

#### `job_delete` — 删除定时任务

| detail 字段 | 类型 | 说明 |
|------------|------|------|
| `job_id` | string | 任务 ID |

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "删除任务",
  "type": "job_delete",
  "detail": {
    "job_id": "a1b2c3d4e5f6"
  }
}
```

#### `job_pause` — 暂停定时任务

| detail 字段 | 类型 | 说明 |
|------------|------|------|
| `job_id` | string | 任务 ID |

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "暂停任务",
  "type": "job_pause",
  "detail": {
    "job_id": "a1b2c3d4e5f6"
  }
}
```

#### `job_resume` — 恢复定时任务

| detail 字段 | 类型 | 说明 |
|------------|------|------|
| `job_id` | string | 任务 ID |

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "恢复任务",
  "type": "job_resume",
  "detail": {
    "job_id": "a1b2c3d4e5f6"
  }
}
```

#### `job_run` — 手动触发执行任务

| detail 字段 | 类型 | 说明 |
|------------|------|------|
| `job_id` | string | 任务 ID |

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "运行任务",
  "type": "job_run",
  "detail": {
    "job_id": "a1b2c3d4e5f6"
  }
}
```

---

### 7. 响应管理类

#### `response_delete` — 删除 API 响应记录

| detail 字段 | 类型 | 说明 |
|------------|------|------|
| `response_id` | string | 被删除的响应 ID |

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "删除响应",
  "type": "response_delete",
  "detail": {
    "response_id": "resp_abc123"
  }
}
```

---

### 8. 会话管理类

#### `run_start` — 启动 Agent 会话

| detail 字段 | 类型 | 说明 |
|------------|------|------|
| `run_id` | string | 运行 ID |
| `session_id` | string | 会话 ID |
| `model` | string | 使用的模型名 |

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "启动会话",
  "type": "run_start",
  "detail": {
    "run_id": "run_a1b2c3d4e5f6",
    "session_id": "sess_abc123",
    "model": "deepseek-v4-flash"
  }
}
```

#### `run_stop` — 停止 Agent 会话

| detail 字段 | 类型 | 说明 |
|------------|------|------|
| `run_id` | string | 运行 ID |

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "停止会话",
  "type": "run_stop",
  "detail": {
    "run_id": "run_a1b2c3d4e5f6"
  }
}
```

#### `run_approval` — 审批操作

| detail 字段 | 类型 | 说明 |
|------------|------|------|
| `run_id` | string | 运行 ID |
| `choice` | string | 审批选择（`once`/`session`/`always`/`deny`） |
| `resolved` | int | 解决的审批数量 |

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "审批操作",
  "type": "run_approval",
  "detail": {
    "run_id": "run_a1b2c3d4e5f6",
    "choice": "once",
    "resolved": 1
  }
}
```

---

### 9. 审计日志管理类

#### `audit_log_clear` — 清空审计日志

| detail 字段 | 类型 | 说明 |
|------------|------|------|
| `cleared_by` | string | 操作来源（`api` 或 `hub_api`） |

```json
{
  "time": "2026-06-09 10:00:00",
  "action": "清空审计日志",
  "type": "audit_log_clear",
  "detail": {
    "cleared_by": "api"
  }
}
```

---

## 完整响应示例

```json
{
  "total": 25,
  "offset": 0,
  "limit": 20,
  "entries": [
    {
      "time": "2026-06-09 10:05:37",
      "action": "用户提问",
      "type": "user_message",
      "detail": {
        "question": "你好",
        "answer_preview": "你好！我是湘信AI2.0...",
        "session_id": "abc123"
      }
    },
    {
      "time": "2026-06-09 10:05:33",
      "action": "工具调用",
      "type": "tool_usage",
      "detail": {
        "tool_name": "web_search",
        "task_id": "run_abc123",
        "duration_ms": 1234,
        "is_error": false
      }
    },
    {
      "time": "2026-06-09 10:03:00",
      "action": "模式修改",
      "type": "security_mode_change",
      "detail": {
        "before": "trust",
        "after": "strict",
        "mode": "strict",
        "previous_mode": "trust"
      }
    }
  ]
}
```

## 请求示例

```bash
# 查询所有日志（最近 20 条）
curl http://127.0.0.1:8642/api/audit/log

# 按类型过滤（如只查工具调用）
curl "http://127.0.0.1:8642/api/audit/log?type=tool_usage"

# 按类型过滤（查对话记录）
curl "http://127.0.0.1:8642/api/audit/log?type=user_message"

# 时间范围过滤
curl "http://127.0.0.1:8642/api/audit/log?since=2026-06-09T00:00:00&until=2026-06-10T00:00:00"

# 分页
curl "http://127.0.0.1:8642/api/audit/log?offset=0&limit=10"
```

## DELETE /api/audit/log

清空所有审计日志条目。

```bash
curl -X DELETE http://127.0.0.1:8642/api/audit/log
```

### 响应

```json
{
  "message": "Audit log cleared"
}
```

## 配置

审计日志配置在 `~/.hermes/config.yaml` 的 `audit_log` 节：

```yaml
audit_log:
  enabled: true          # 是否启用审计日志（默认 true）
  max_entries: 1000      # 最大保留条数，超出则删除最旧条目
  retention_days: 30     # 保留天数，0 表示不限
```

## 存储

日志以 JSON lines 格式存储在 `~/.hermes/audit_log.json`，每条日志一行 JSON。
每次写入时自动执行保留策略清理（按 retention_days 和 max_entries）。
