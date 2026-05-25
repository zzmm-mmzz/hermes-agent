# 工作目录管理 API

## 概述

工作目录管理 API 用于获取和设置 Hermes Agent 的运行时工作目录（进程级 `os.getcwd()`）。

## 端点清单

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/workdir` | 获取当前工作目录 |
| POST | `/api/workdir` | 设置当前工作目录 |

## 认证

所有请求需要通过 API 密钥认证，通过 `Authorization: Bearer <token>` 或 `X-API-Key` 请求头发送。

## 获取工作目录

```
GET /api/workdir
```

### 请求示例

```bash
curl http://127.0.0.1:8642/api/workdir \
  -H "Authorization: Bearer your-api-key"
```

### 响应示例

```json
{
  "workdir": "G:\\hermes agent\\hermes-agent",
  "project_root": "G:\\hermes agent\\hermes-agent"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `workdir` | string | 进程当前工作目录（`os.getcwd()`） |
| `project_root` | string | Hermes Agent 项目根目录（固定值，用于参考对比） |

## 设置工作目录

```
POST /api/workdir
Content-Type: application/json

{
  "workdir": "/path/to/directory"
}
```

### 请求体参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `workdir` | string | 是 | 目标工作目录路径。支持绝对路径、相对路径、`~` 展开 |

### 路径处理规则

- 支持 `~` 展开为用户家目录
- 相对路径基于当前工作目录解析
- Windows 反斜杠路径自动标准化
- 路径必须 **已存在** 于文件系统上
- 通过 `os.chdir()` 实时生效，仅影响当前进程

### 请求示例

```bash
# 设置为项目目录
curl -X POST http://127.0.0.1:8642/api/workdir \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"workdir": "G:\\hermes agent\\hermes-agent"}'

# 设置到家目录下的某个项目
curl -X POST http://127.0.0.1:8642/api/workdir \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"workdir": "~/projects/my-project"}'

# 使用正斜杠路径（同样支持）
curl -X POST http://127.0.0.1:8642/api/workdir \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"workdir": "C:/Users/27430/projects/my-project"}'
```

### 成功响应

```json
{
  "message": "Working directory changed to: G:\\hermes agent\\hermes-agent",
  "workdir": "G:\\hermes agent\\hermes-agent"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `message` | string | 操作描述 |
| `workdir` | string | 设置后的当前工作目录 |

### 错误响应

**400 — 参数缺失或路径不存在**

```json
{
  "error": "Provide 'workdir' (string, non-empty path)"
}
```

```json
{
  "error": "Directory does not exist: G:\\nonexistent\\path"
}
```

```json
{
  "error": "Invalid JSON body"
}
```

**403 — 权限不足**

```json
{
  "error": "Permission denied: C:\\Windows\\System32"
}
```

## 注意事项

1. **进程级生效**：`os.chdir()` 改变的是整个 Python 进程的工作目录，后续所有相对路径操作都基于该目录。
2. **不持久化**：此 API 不修改 `config.yaml`，重启 Hermes Agent 后工作目录恢复为启动目录。
3. **影响范围**：设置的工作目录会影响该进程中运行的 cron 任务、子进程等工作目录相关的行为。
4. **项目根目录不变**：`project_root` 在 GET 响应中作为参考返回，它是 Hermes Agent 代码目录，不受 SET 操作影响。

## 与其他 API 的关系

- 配合 `/api/sandbox` 使用：设置工作目录后再开启沙箱，可以控制沙箱环境的默认工作路径
- 配合 `/api/security/mode` 使用：安全模式不依赖工作目录，两者独立
