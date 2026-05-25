# 沙箱环境 API 文档

## 概述

沙箱环境 API 提供了对 Hermes Agent 终端执行后端的管理接口，支持在隔离的沙箱环境（Docker、Vercel Sandbox 等）和本地执行之间切换。

沙箱环境的核心是切换 `terminal.backend` 配置值。

| Backend | 是否沙箱 | 说明 |
|---------|----------|------|
| `local` | 否 | 直接在宿主机执行命令 |
| `docker` | 是 | Docker 容器中运行 |
| `vercel_sandbox` | 是 | Vercel Sandbox (node24 runtime) |
| `ssh` | 是 | 远程 SSH 主机 |
| `singularity` | 是 | Singularity 容器 |
| `modal` | 是 | Modal serverless 平台 |
| `daytona` | 是 | Daytona 工作空间 |

所有接口均需要 API 认证（如果配置了 `API_SERVER_KEY`），通过 `Authorization: Bearer <key>` 请求头传递。

Base URL: `http://127.0.0.1:8642`

---

## 1. 获取沙箱状态

**GET** `/api/sandbox`

获取当前沙箱环境的开启状态、后端类型和相关配置。

### 请求示例

```bash
curl http://127.0.0.1:8642/api/sandbox
```

带认证：
```bash
curl -H "Authorization: Bearer <your-api-key>" http://127.0.0.1:8642/api/sandbox
```

### 响应示例

```json
{
  "sandbox_enabled": false,
  "backend": "local",
  "available_backends": [
    "daytona",
    "docker",
    "local",
    "modal",
    "singularity",
    "ssh",
    "vercel_sandbox"
  ],
  "settings": {
    "backend": "local",
    "docker_image": "nikolaik/python-nodejs:python3.11-nodejs20",
    "vercel_runtime": "node24",
    "container_cpu": 1,
    "container_memory": 5120,
    "container_disk": 51200,
    "container_persistent": true
  }
}
```

### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `sandbox_enabled` | bool | 是否启用了沙箱环境（`local` 为 false，其余为 true） |
| `backend` | string | 当前终端执行后端 |
| `available_backends` | array | 支持的所有后端列表 |
| `settings.backend` | string | 当前后端 |
| `settings.docker_image` | string | Docker 镜像 |
| `settings.vercel_runtime` | string | Vercel 运行时 |
| `settings.container_cpu` | int | 容器 CPU 核心数 |
| `settings.container_memory` | int | 容器内存限制（MB） |
| `settings.container_disk` | int | 容器磁盘限制（MB） |
| `settings.container_persistent` | bool | 容器文件系统是否跨会话持久化 |

---

## 2. 设置沙箱环境

**POST** `/api/sandbox`

开启或关闭沙箱环境，或直接指定具体的终端执行后端。

### 请求体格式

#### 使用 boolean 开关

```json
{
  "sandbox_enabled": true
}
```

开启沙箱时，默认切换到 `vercel_sandbox` 后端（docker 不可用时）。

```json
{
  "sandbox_enabled": false
}
```

关闭沙箱时切换回 `local` 后端，并自动记录之前的后端到 `previous_backend` 字段。

#### 直接指定后端

```json
{
  "backend": "docker"
}
```

```json
{
  "backend": "vercel_sandbox"
}
```

### 请求字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `sandbox_enabled` | bool | 与 backend 二选一 | `true` 开启沙箱，`false` 关闭沙箱 |
| `backend` | string | 与 sandbox_enabled 二选一 | 直接指定后端类型 |

### 响应示例

开启沙箱：
```json
{
  "message": "Sandbox backend set to 'vercel_sandbox'",
  "sandbox_enabled": true,
  "backend": "vercel_sandbox"
}
```

关闭沙箱：
```json
{
  "message": "Sandbox backend set to 'local'",
  "sandbox_enabled": false,
  "backend": "local"
}
```

### 错误响应示例

无效后端：
```json
{
  "error": "Invalid backend 'invalid_backend'. Must be one of: daytona, docker, local, modal, singularity, ssh, vercel_sandbox"
}
```

缺少必要参数：
```json
{
  "error": "Provide either 'sandbox_enabled' (bool) or 'backend' (string)"
}
```

---

## 使用示例

### 查看当前沙箱状态

```bash
curl -s http://127.0.0.1:8642/api/sandbox | python -m json.tool
```

### 开启沙箱（切换到 Vercel Sandbox）

```bash
curl -s -X POST http://127.0.0.1:8642/api/sandbox \
  -H "Content-Type: application/json" \
  -d '{"sandbox_enabled": true}' | python -m json.tool
```

### 关闭沙箱（切换回本地执行）

```bash
curl -s -X POST http://127.0.0.1:8642/api/sandbox \
  -H "Content-Type: application/json" \
  -d '{"sandbox_enabled": false}' | python -m json.tool
```

### 切换到 Docker 沙箱

```bash
curl -s -X POST http://127.0.0.1:8642/api/sandbox \
  -H "Content-Type: application/json" \
  -d '{"backend": "docker"}' | python -m json.tool
```
