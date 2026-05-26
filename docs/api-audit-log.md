# 审计日志 API

查询和清空 Hermes Agent 的安全审计日志。

## GET /api/audit/log

获取审计日志条目。

### 查询参数

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `type` | string | 可选 | 按事件类型过滤 |
| `since` | string | 可选 | ISO 时间戳，包含此时间之后的条目 |
| `until` | string | 可选 | ISO 时间戳，包含此时间之前的条目 |
| `offset` | int | 0 | 分页偏移 |
| `limit` | int | 20 | 每页条数（最大 200） |

### 事件类型

| 事件类型 | 说明 |
|---------|------|
| `security_mode_change` | 安全模式切换 |
| `sandbox_change` | 沙箱环境切换 |
| `workdir_change` | 路径白名单变更 |

### 示例

```bash
# 查询所有日志（最近 20 条）
curl http://127.0.0.1:8642/api/audit/log

# 按类型过滤
curl "http://127.0.0.1:8642/api/audit/log?type=security_mode_change"

# 时间范围过滤
curl "http://127.0.0.1:8642/api/audit/log?since=2026-05-25T00:00:00&until=2026-05-26T00:00:00"

# 分页
curl "http://127.0.0.1:8642/api/audit/log?offset=0&limit=10"
```

### 响应格式

```json
{
  "total": 3,
  "offset": 0,
  "limit": 20,
  "entries": [
    {
      "operate_time": "2026-05-26 17:00:59",
      "operate_type": "模式修改",
      "raw_type": "security_mode_change",
      "before_value": "trust",
      "after_value": "strict",
      "detail": {
        "mode": "strict",
        "previous_mode": "trust"
      }
    }
  ]
}
```

## DELETE /api/audit/log

清空所有审计日志条目。

### 示例

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
  enabled: true          # 是否启用审计日志
  max_entries: 1000      # 最大保留条数，超出则删除最旧条目
  retention_days: 30     # 保留天数，0 表示不限
```

## 存储

日志以 JSON lines 格式存储在 `~/.hermes/audit_log.json`，每条日志一行 JSON。
每次写入时自动执行保留策略清理。
