# 安全模式 API 文档

## 概述

安全模式 API 提供了对 Hermes Agent 安全配置的管理接口，支持五种预设安全模式以及自定义设置。

所有接口均需要 API 认证（如果配置了 `API_SERVER_KEY`），通过 `Authorization: Bearer <key>` 请求头传递。

Base URL: `http://127.0.0.1:8642`

---

## 1. 获取当前安全模式

**GET** `/api/security/mode`

获取当前的安全模式预设及其详细配置。

### 请求示例

```bash
curl http://127.0.0.1:8642/api/security/mode
```

带认证：
```bash
curl -H "Authorization: Bearer your-api-key" http://127.0.0.1:8642/api/security/mode
```

### 响应示例

```json
{
  "mode": "protection",
  "settings": {
    "allow_private_urls": false,
    "redact_secrets": true,
    "tirith_enabled": true,
    "tirith_path": "tirith",
    "tirith_timeout": 5,
    "tirith_fail_open": true,
    "approval_required": true
  }
}
```

### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `mode` | string | 当前安全模式预设，取值 `trust` / `protection` / `strict` / `off` / `custom` |
| `settings.allow_private_urls` | bool | 是否允许请求私有/内网 IP 地址 |
| `settings.redact_secrets` | bool | 是否在工具输出中自动遮盖密钥 |
| `settings.tirith_enabled` | bool | 是否启用 Tirith 预执行安全扫描 |
| `settings.tirith_path` | string | Tirith 二进制的路径 |
| `settings.tirith_timeout` | int | Tirith 扫描超时时间（秒） |
| `settings.tirith_fail_open` | bool | Tirith 扫描失败时是否放行 |
| `settings.approval_required` | bool | 是否需要对危险命令进行确认审批 |

---

## 2. 设置安全模式

**POST** `/api/security/mode`

设置安全模式预设或自定义安全配置。

### 请求体格式

#### 使用预设模式

```json
{
  "mode": "protection"
}
```

#### 使用自定义模式

```json
{
  "mode": "custom",
  "settings": {
    "allow_private_urls": true,
    "redact_secrets": true,
    "tirith_enabled": false,
    "tirith_fail_open": true,
    "approval_required": false
  }
}
```

### 请求示例

```bash
curl -X POST http://127.0.0.1:8642/api/security/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "strict"}'
```

带认证：
```bash
curl -X POST http://127.0.0.1:8642/api/security/mode \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"mode": "trust"}'
```

### 响应示例

```json
{
  "message": "Security mode set to 'strict'",
  "mode": "strict",
  "settings": {
    "allow_private_urls": false,
    "redact_secrets": true,
    "tirith_enabled": true,
    "tirith_fail_open": false,
    "approval_required": true
  }
}
```

### 错误响应

```json
{
  "error": "Invalid mode 'unknown'. Must be one of: custom, off, protection, strict, trust"
}
```

### 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 设置成功 |
| 400 | 请求参数错误（无效的mode、缺少mode等） |
| 401 | 未授权（需要API Key） |

---

## 安全模式预设说明

| 模式值 | 名称（中文） | 说明 | 关键配置 |
|--------|-------------|------|---------|
| `trust` | 信任方案 | 最小限制，充分信任代理 | 允许内网URL、不遮盖密钥、关闭Tirith、关闭命令审批 |
| `protection` | 保护方案 | 均衡保护（默认） | 遮盖密钥、启用Tirith（失败时放行）、需要命令审批 |
| `strict` | 严格方案 | 最大安全限制 | 遮盖密钥、启用Tirith（失败时阻止）、需要命令审批、禁止内网URL |
| `off` | 关闭方案 | 关闭所有安全措施 | 允许内网URL、不遮盖密钥、关闭Tirith、关闭命令审批 |
| `custom` | 自定义方案 | 用户自定义每一项设置 | 通过 `settings` 字段逐项指定 |

### 预设模式的具体配置值对照表

| 配置项 | trust | protection | strict | off |
|--------|-------|------------|--------|-----|
| `allow_private_urls` | true | false | false | true |
| `redact_secrets` | false | true | true | false |
| `tirith_enabled` | false | true | true | false |
| `tirith_fail_open` | true | true | false | true |
| `approval_required` | false | true | true | false |

---

## 注意事项

1. 所有修改会立即写入到 `~/.hermes/config.yaml` 文件的 `security` 节。
2. 配置更改对于正在运行中的网关进程是即时生效的（配置读写不走缓存路径 `load_config_readonly`，而是通过 `load_config` + `save_config` 直接操作文件系统）。
3. `custom` 模式下，未在 `settings` 中指定的字段会保留当前值不变。
4. 如果在网关启动时通过环境变量（`API_SERVER_KEY`）配置了认证密钥，所有 `/api/security/mode` 请求都必须在请求头中携带 `Authorization: Bearer <key>`。
