# 路径白名单管理 API

## 概述

管理 Hermes Agent 的安全路径白名单（allowed_paths）。白名单定义了 Hermes 可以读写哪些目录，是安全系统的一部分，存储在 `config.yaml` 的 `security.allowed_paths` 字段中。

## GET /api/workdir

获取当前的路径白名单和工作目录。

### 请求

```bash
curl http://127.0.0.1:8642/api/workdir
```

### 响应示例

```json
{
  "allowed_paths": ["~"],
  "expanded_paths": ["C:\\Users\\27430"],
  "workdir": "G:\\hermes agent\\hermes-agent",
  "project_root": "G:\\hermes agent\\hermes-agent"
}
```

| 字段 | 说明 |
|------|------|
| `allowed_paths` | 配置中保存的原始白名单路径列表（可能含 `~`） |
| `expanded_paths` | `~` 展开后的实际绝对路径列表 |
| `workdir` | 当前进程的实际工作目录（`os.getcwd()`） |
| `project_root` | 项目根目录 |

## POST /api/workdir

设置路径白名单。

### 请求体格式

```json
{
  "allowed_paths": ["G:\\hermes agent\\hermes-agent", "~"]
}
```

支持多路径，`~` 会自动展开为用户家目录。

传空数组表示不限制任何路径：

```json
{
  "allowed_paths": []
}
```

### 响应示例（成功）

```json
{
  "message": "Path whitelist updated",
  "allowed_paths": [
    "G:\\hermes agent\\hermes-agent",
    "C:\\Users\\27430"
  ]
}
```

### 响应示例（部分路径不存在）

```json
{
  "message": "Path whitelist updated",
  "allowed_paths": [
    "G:\\hermes agent\\hermes-agent"
  ],
  "errors": [
    "Directory does not exist: C:\\non_existent_dir"
  ]
}
```

不存在的路径会被跳过并列出在 `errors` 数组中，状态码返回 207。

## 五种模式的默认白名单

| 模式 | 默认白名单 |
|------|-----------|
| `trust` | `["~"]` — 用户家目录 |
| `protection` | `["~"]` — 用户家目录 |
| `strict` | `["~"]` — 用户家目录 |
| `off` | `["~"]` — 用户家目录 |
| `custom` | `["~"]` — 用户家目录 |

白名单与安全模式是独立的设置，仅在 `protection` 和 `strict` 模式下生效。

## 错误码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 207 | 部分路径不存在（白名单已保存） |
| 400 | 请求体格式错误（需要 `allowed_paths` 数组） |
| 401 | 缺少认证头 |
| 403 | 权限不足 |
| 500 | 服务器内部错误 |
