# Hermes SkillHub API 接口文档

> Hub API Server 运行在 `http://localhost:8642`
> 源码文件: `hub_api_server.py`
> 用途: 提供技能市场浏览、安装、卸载、上传功能，与自建 SkillHub (`http://localhost:8080`) 集成

---

## 目录

- [1. 获取全部技能列表](#1-获取全部技能列表)
- [2. 获取已安装技能列表](#2-获取已安装技能列表)
- [3. 安装技能](#3-安装技能)
- [4. 卸载技能](#4-卸载技能)
- [5. 上传技能](#5-上传技能)
- [附录](#附录)

---

## 1. 获取全部技能列表

从 SkillHub 获取所有可用技能。

```
GET /api/skills
```

### 请求参数（可选）

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `installed` | string | 不传 | 过滤已安装状态，`true` / `1` / `yes` 只保留已安装，`false` / `0` / `no` 只保留未安装 |

### 请求示例

```bash
# 查全部
curl http://localhost:8642/api/skills

# 只看已安装
curl http://localhost:8642/api/skills?installed=true

# 只看未安装
curl http://localhost:8642/api/skills?installed=false
```

### 响应示例

```json
{
  "skills": [
    {
      "slug": "data-analyzer",
      "name": "data-analyzer",
      "description": "数据分析和可视化助手——快速分析 CSV/Excel 数据并生成报告",
      "version": "1.0.0",
      "tags": [],
      "installed": false
    },
    {
      "slug": "hello-world",
      "name": "hello-world",
      "description": "A simple hello world test skill for verifying SkillHub integration",
      "version": "1.0.0",
      "tags": [],
      "installed": true
    }
  ],
  "total": 2
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `slug` | string | 技能唯一标识符，用于安装/卸载操作 |
| `name` | string | 技能显示名称 |
| `description` | string | 技能描述 |
| `version` | string | 最新版本号 |
| `tags` | string[] | 技能标签列表 |
| `installed` | boolean | 是否已安装到本地 |
| `total` | number | 技能总数 |

---

## 2. 获取已安装技能列表

扫描 `~/.hermes/skills/` 目录，返回本地已安装的所有技能。

```
GET /api/skills/installed
```

### 请求示例

```bash
curl http://localhost:8642/api/skills/installed
```

### 响应示例

```json
{
  "skills": [
    {
      "name": "hello-world",
      "slug": "hello-world",
      "description": "A simple hello world test skill for verifying SkillHub integration",
      "category": "self-hosted",
      "path": "C:\\Users\\27430\\.hermes\\skills\\self-hosted\\hello-world"
    }
  ],
  "total": 1
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 技能显示名称（从 SKILL.md frontmatter 解析） |
| `slug` | string | 技能目录名，也是 SkillHub 上的 slug |
| `description` | string | 技能描述 |
| `category` | string | 分类目录名 |
| `path` | string | 技能在磁盘上的绝对路径 |
| `total` | number | 已安装技能总数 |

---

## 3. 安装技能

从 SkillHub 下载技能 ZIP 包，解压安装到本地 `~/.hermes/skills/` 目录。

```
POST /api/skills/install
Content-Type: application/json
```

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `slug` | string | 是 | 技能的唯一标识符（从列表接口获取） |
| `version` | string | 否 | 指定版本，不传则安装最新版 |

### 请求示例

```bash
curl -X POST http://localhost:8642/api/skills/install \
  -H "Content-Type: application/json" \
  -d '{"slug": "data-analyzer"}'
```

指定版本:

```bash
curl -X POST http://localhost:8642/api/skills/install \
  -H "Content-Type: application/json" \
  -d '{"slug": "data-analyzer", "version": "1.0.0"}'
```

### 成功响应 (200)

```json
{
  "ok": true,
  "message": "技能 'data-analyzer' 安装成功 (v1.0.0)"
}
```

### 重复安装 (409)

```json
{
  "ok": false,
  "message": "技能 'hello-world' 已安装"
}
```

### 技能不存在 (500)

```json
{
  "ok": false,
  "message": "技能 'nonexistent' 在 SkillHub 上未找到"
}
```

### 缺少参数 (400)

```json
{
  "ok": false,
  "message": "缺少 slug 参数"
}
```

---

## 4. 卸载技能

从本地 `~/.hermes/skills/` 目录删除指定技能的整个目录。

```
POST /api/skills/uninstall
Content-Type: application/json
```

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `slug` | string | 是 | 要卸载的技能标识符 |

### 请求示例

```bash
curl -X POST http://localhost:8642/api/skills/uninstall \
  -H "Content-Type: application/json" \
  -d '{"slug": "data-analyzer"}'
```

### 成功响应 (200)

```json
{
  "ok": true,
  "message": "技能 'data-analyzer' 卸载成功"
}
```

### 未安装 (404)

```json
{
  "ok": false,
  "message": "技能 'nonexistent' 未安装"
}
```

### 缺少参数 (400)

```json
{
  "ok": false,
  "message": "缺少 slug 参数"
}
```

---

## 5. 上传技能

将 ZIP 包上传到自建 SkillHub，技能默认公开（PUBLIC），所有人可见。

```
POST /api/skills/upload
Content-Type: multipart/form-data
```

### 请求参数（multipart/form-data）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | file | 是 | ZIP 格式的技能包，根目录需包含 `SKILL.md` |

### 请求示例

```bash
# 1. 打包技能
mkdir my-skill
cat > my-skill/SKILL.md << 'EOF'
---
name: my-awesome-skill
description: 一个很棒的新技能
version: 1.0.0
---
# My Awesome Skill
EOF

cd my-skill && zip -r ../my-skill.zip .

# 2. 上传
curl -X POST http://localhost:8642/api/skills/upload \
  -F "file=@my-skill.zip"
```

### 成功响应 (200)

```json
{
  "ok": true,
  "status": 200,
  "response": {
    "code": 200,
    "msg": "发布成功",
    "data": {
      "slug": "my-awesome-skill",
      "version": "1.0.0"
    }
  }
}
```

### 文件无效 (400)

```json
{
  "ok": false,
  "message": "文件内容为空"
}
```

---

## 附录

### 安装目录结构

技能安装到 `~/.hermes/skills/` 后，目录结构如下：

```
~/.hermes/skills/
├── self-hosted/
│   ├── hello-world/
│   │   └── SKILL.md
│   └── data-analyzer/
│       └── SKILL.md
├── apple/
│   ├── apple-notes/
│   │   └── SKILL.md
│   └── ...
└── ...
```

### 配置说明

新建 `hub_config.yaml` 在 `hub_api_server.py` 同级目录下（源码根目录）：

```yaml
skillhub:
  base_url: "http://localhost:8080/api/v1"
  username: "local-admin"         # 上传用的用户名（local 模式用 mock 用户 ID）
  password: ""                    # 密码（留空使用 local mock auth）
  upload:
    namespace: "global"
    visibility: "PUBLIC"

server:
  host: "127.0.0.1"
  port: 8642
```

**认证策略：**
- `password` 为空：使用 `X-Mock-User-Id` 头（local 开发模式）
  - `local-admin` = 超级管理员
  - `local-user` = 普通用户
- `password` 不为空：先调用 `/api/v1/auth/direct/login` 获取 session，再用 session 上传

### 启动服务

```bash
cd G:\hermes agent\hermes-agent
source .venv/Scripts/activate
python hub_api_server.py 8642
```

### 服务状态

```
GET /health
```

```json
{
  "status": "ok",
  "service": "hermes-hub-api"
}
```

### 技术栈

- **框架:** aiohttp (Python)
- **端口:** 8642
- **CORS:** 全放通（`Access-Control-Allow-Origin: *`）
- **SkillHub 地址:** `http://localhost:8080/api/v1`
- **技能目录:** `~/.hermes/skills/`
