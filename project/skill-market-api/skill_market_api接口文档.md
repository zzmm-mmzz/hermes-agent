# Hermes Skill Market API 接口文档

> 文件: `skill_market_api.py`
> 启动: `python skill_market_api.py [port]`
> 默认地址: `http://127.0.0.1:8643`
> 路由前缀: `/api/skill-market/`

---

## 目录

1. [查询市场技能](#1-查询市场技能)
2. [查询本地技能](#2-查询本地技能)
3. [查询本地技能详情](#3-查询本地技能详情)
4. [下载技能 ZIP（代理）](#4-下载技能-zip代理)
5. [安装技能](#5-安装技能)
6. [卸载技能](#6-卸载技能)
7. [导入个人技能](#7-导入个人技能)
8. [健康检查](#8-健康检查)
9. [统一响应结构](#9-统一响应结构)
10. [技能数据模型](#10-技能数据模型)

---

## 1. 查询市场技能

从后端技能市场（ClientController）获取全量技能列表，支持按安装状态过滤。

- **Method**: `GET`
- **Path**: `/api/skill-market/list`

### Query 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `installed` | `string` | 否 | 按安装状态过滤。不传=全部；`true`=已安装到本地；`false`=未安装到本地 |
| `visibility` | `string` | 否 | 按可见性过滤。如 `private`、`public` |

### 调用示例

```http
# 获取全部市场技能
GET /api/skill-market/list

# 仅获取已安装的市场技能
GET /api/skill-market/list?installed=true

# 仅获取未安装的市场技能
GET /api/skill-market/list?installed=false

# 组合过滤
GET /api/skill-market/list?installed=false&visibility=private
```

### 成功响应

```json
{
  "code": "0000",
  "message": "成功",
  "total": 2,
  "data": [
    {
      "id": "skill-001",
      "name": "PDF 处理工具",
      "slug": "pdf-tool",
      "namespaceId": "ns-001",
      "namespaceName": "self-hosted",
      "description": "处理 PDF 文件的技能",
      "visibility": "private",
      "status": "active",
      "currentVersion": "1.0.0",
      "latestVersion": "1.3.0",
      "lastVersionId": "ver-1.3.0",
      "downloadCount": 120,
      "starCount": 5,
      "ratingAvg": 4.8,
      "ratingCount": 10,
      "tags": ["pdf", "document"],
      "createTime": "2025-01-10T08:00:00Z",
      "updateTime": "2025-06-20T10:30:00Z",
      "createNo": "admin"
    }
  ]
}
```

---

## 2. 查询本地技能

查询当前用户 `~/.hermes/skills/` 下已安装的个人技能，**不请求后端**。

- **Method**: `GET`
- **Path**: `/api/skill-market/local`

### Query 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `visibility` | `string` | 否 | 按可见性过滤。如 `private`、`public` |

### 调用示例

```http
# 获取全部本地技能
GET /api/skill-market/local

# 仅获取私有的本地技能
GET /api/skill-market/local?visibility=private
```

### 成功响应

```json
{
  "code": "0000",
  "message": "成功",
  "total": 1,
  "data": [
    {
      "id": "local-self-hosted-my-custom-skill",
      "name": "My Custom Skill",
      "slug": "my-custom-skill",
      "namespaceId": "local",
      "namespaceName": "self-hosted",
      "description": "本地创建的个人技能",
      "visibility": "personal",
      "status": "active",
      "currentVersion": "",
      "downloadCount": 0,
      "starCount": 0,
      "ratingAvg": 0.0,
      "ratingCount": 0,
      "latestVersion": "",
      "lastVersionId": "",
      "tags": [],
      "createTime": "",
      "updateTime": "",
      "createNo": "local",
      "_source": "local"
    }
  ]
}
```

> 本地技能数据来源于 `SKILL.md` 文件的 frontmatter（name、description、visibility 字段）。

---

## 3. 查询本地技能详情

查询指定本地技能的详细信息，包括目录文件结构（fileTree）、文本文件内容（fileContents）、完整 SKILL.md 解析（frontmatter + body）。

- **Method**: `GET`
- **Path**: `/api/skill-market/local/{slug}/detail`

### Path 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `slug` | `string` | 是 | 技能 slug（目录名，如 `dianfei-cuishou`） |

### 调用示例

```http
GET /api/skill-market/local/dianfei-cuishou/detail
```

### 成功响应（HTTP 200）

```json
{
  "code": "0000",
  "message": "成功",
  "data": {
    "slug": "dianfei-cuishou",
    "name": "实时电费催收全流程自动化",
    "description": "实时电费催收全流程自动化：查询欠费用户 → 实时催费工单批量导入 → 完结",
    "visibility": "personal",
    "version": "",
    "author": "",
    "namespaceName": "default",
    "tags": [],
    "frontmatter": {
      "name": "实时电费催收全流程自动化",
      "description": "实时电费催收全流程自动化：...",
      "version": ""
    },
    "body": "# 技能名称\n\n实时电费催收全流程自动化：...",
    "fileTree": [
      { "path": ".env", "size": 233 },
      { "path": "SKILL.md", "size": 13878 },
      { "path": "run.py", "size": 1171 },
      { "path": "scripts/create_workst.py", "size": 7123 },
      { "path": "scripts/owe_fee.py", "size": 5234 },
      { "path": "scripts/utils.py", "size": 3456 }
    ],
    "fileContents": {
      "SKILL.md": "---\nname: 实时电费催收全流程自动化\n...",
      "run.py": "import json\nfrom hermes_tools import terminal\n..."
    },
    "readmeSize": 12000,
    "fileCount": 6
  }
}
```

### 失败响应（HTTP 404）

```json
{
  "code": "404",
  "message": "技能 'not-exist' 未安装"
}
```

### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `slug` | `string` | 技能目录名 |
| `name` | `string` | 技能显示名称（来自 SKILL.md frontmatter） |
| `description` | `string` | 技能描述 |
| `visibility` | `string` | 可见性：`personal`、`private`、`public` |
| `version` | `string` | 版本号 |
| `author` | `string` | 作者 |
| `namespaceName` | `string` | 所属分类目录名称（如 `default`、`creative`、`mcp`） |
| `tags` | `array[string]` | 标签列表 |
| `frontmatter` | `object` | SKILL.md 完整 YAML frontmatter（解析为字典，支持嵌套键） |
| `body` | `string` | SKILL.md 正文内容（frontmatter 之后的部分） |
| `fileTree` | `array` | 技能目录下的文件清单，每项包含 `path`（相对路径）和 `size`（字节数） |
| `fileContents` | `object` | 文本文件内容字典，key=相对路径，value=前 3000 字符。SKILL.md、`.py`、`.json`、`.yaml`、`.env` 等常见文本文件自动读取，二进制文件跳过。`__pycache__` 目录自动排除 |
| `readmeSize` | `number` | SKILL.md 正文的字符数 |
| `fileCount` | `number` | 技能目录下的文件总数 |

### 查找规则

在所有分类目录下搜索匹配 slug 的技能目录：

```
~/.hermes/skills/
├── default/dianfei-cuishou/   ← 命中
├── creative/*/
├── mcp/*/
└── 公共/*/
```

扁平结构（slug 直接作为 skills/ 的一级子目录）和分类结构（slug 在分类子目录下）均支持。

---

## 4. 下载技能 ZIP（代理）

代理下载指定版本的技能 ZIP 包。服务端转发请求到后端 ClientController。

- **Method**: `GET`
- **Path**: `/api/skill-market/skills/{skillId}/versions/{versionId}/download`

### Path 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `skillId` | `string` | 是 | 技能 ID |
| `versionId` | `string` | 是 | 版本 ID |

### 调用示例

```http
GET /api/skill-market/skills/skill-001/versions/ver-1.3.0/download
```

### 成功响应

- **Content-Type**: `application/zip`
- **Content-Disposition**: `attachment; filename="skill_001_ver_1.3.0.zip"`

返回 ZIP 二进制流，前端直接触发浏览器下载。

### 失败响应

```json
{
  "code": "400",
  "message": "缺少 skillId 或 versionId 参数"
}
```

---

## 4. 安装技能

从后端市场下载技能 ZIP 并安装到本地 `~/.hermes/skills/<namespace>/<slug>/`。

- **Method**: `POST`
- **Path**: `/api/skill-market/install`
- **Content-Type**: `application/json`

### Request Body

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `skillId` | `string` | 是 | 技能 ID（市场列表中 `id` 字段） |
| `versionId` | `string` | 否 | 版本 ID。不传则使用市场中的 `lastVersionId` |
| `version` | `string` | 否 | 语义化版本号（仅用于显示，如 `1.3.0`） |

### 调用示例

```http
POST /api/skill-market/install
Content-Type: application/json

{
  "skillId": "skill-001",
  "versionId": "ver-1.3.0",
  "version": "1.3.0"
}
```

### 成功响应（HTTP 200）

```json
{
  "ok": true,
  "message": "技能 'PDF 处理工具' 安装成功 (v1.3.0)"
}
```

### 失败响应（HTTP 400）

```json
{
  "ok": false,
  "message": "技能 'PDF 处理工具' 已安装"
}
```

```json
{
  "ok": false,
  "message": "下载技能 'pdf-tool' 失败 (versionId=ver-1.3.0)"
}
```

### 安装流程

```
1. 通过 skillId 在市场列表中查找技能详情
   → 获取 slug、namespaceName、lastVersionId
2. 确定 versionId（优先使用传入参数，fallback 到 lastVersionId）
3. 检查本地是否已安装（按 slug 去重）
4. 调用 ClientController 下载接口:
   GET /client/skills/{skillId}/versions/{versionId}/download
5. 解析 ZIP，解压到 ~/.hermes/skills/<namespace>/<slug>/
   - 过滤 >500KB 的文件
   - 防止路径穿越攻击（拒绝包含 ".." 的路径）
```

---

## 5. 卸载技能

从本地 `~/.hermes/skills/` 删除指定技能目录。

- **Method**: `POST`
- **Path**: `/api/skill-market/uninstall`
- **Content-Type**: `application/json`

### Request Body

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `slug` | `string` | 是 | 技能 slug（目录名，不含分类路径） |

### 调用示例

```http
POST /api/skill-market/uninstall
Content-Type: application/json

{
  "slug": "pdf-tool"
}
```

### 成功响应（HTTP 200）

```json
{
  "ok": true,
  "message": "技能 'pdf-tool' 卸载成功"
}
```

### 失败响应（HTTP 404）

```json
{
  "ok": false,
  "message": "技能 'pdf-tool' 未安装"
}
```

### 卸载流程

```
遍历 ~/.hermes/skills/<所有分类目录>/
  匹配 slug → shutil.rmtree() 删除技能目录
  未匹配 → 返回 404
```

---

## 7. 导入个人技能

将外部技能创建/导入到本地 `~/.hermes/skills/` 目录下，作为个人私人技能。**直接写文件系统，不依赖后端市场。**

- **Method**: `POST`
- **Path**: `/api/skill-market/import-local`
- **Content-Type**: `application/json`

### Request Body

| 参数 | 类型 | 必填 | 默认值 | 校验规则 | 说明 |
|------|------|------|--------|----------|------|
| `name` | `string` | **是** | - | 1-64 字符；只能包含小写字母、数字、连字符(`-`)；必须以字母或数字开头和结尾 | 技能目录名（slug），也是技能的唯一标识。如 `my-custom-skill` |
| `content` | `string` | **是** | - | 不能为空字符串或纯空白 | SKILL.md 正文内容（Markdown 格式，不含 YAML frontmatter）。例如 `## 触发条件\n...` |
| `displayName` | `string` | 否 | 同 `name` | 无特殊限制 | 技能显示名称（SKILL.md 中 `name:` 字段），支持中文 |
| `description` | `string` | 否 | `""` | 无特殊限制 | 技能描述，简要说明技能用途 |
| `category` | `string` | 否 | `""` | 只能包含字母、数字、中文和连字符 | 分类目录名。传值则放到 `skills/{category}/{name}/`；留空/不传则放到 `skills/{name}/`（扁平结构） |
| `visibility` | `string` | 否 | `"personal"` | 取值：`personal`、`private`、`public` | 技能可见性 |
| `version` | `string` | 否 | `""` | 无严格校验，建议语义化版本如 `1.0.0` | 版本号 |
| `author` | `string` | 否 | `""` | 无特殊限制 | 作者名称 |
| `tags` | `array[string]` | 否 | `[]` | 数组元素不能为空字符串 | 标签列表，如 `["python", "自动化"]` |
| `files` | `object` | 否 | `{}` | key=相对路径（含 `..` 的路径会被自动跳过）；value=文件内容字符串 | 附加文件字典，每条对应技能目录下的一个文件。如 `{"scripts/run.sh": "echo hello"}` |

> `name` 和 `content` 两个字段**同时必填**，缺一不可。
> `files` 中的路径若包含 `..`（路径穿越）会被自动跳过并记录警告日志，不会导致整体失败。

### 调用示例

```http
# 最小请求
POST /api/skill-market/import-local
Content-Type: application/json

{
  "name": "hello-world",
  "content": "## 触发条件\n\n用户说 hello world\n\n## 执行步骤\n\n1. 打印 Hello World\n2. 完成"
}

# 完整请求
POST /api/skill-market/import-local
Content-Type: application/json

{
  "name": "my-custom-skill",
  "displayName": "我的自定义技能",
  "description": "这是一个测试用的自定义技能",
  "category": "my-tools",
  "visibility": "personal",
  "version": "1.0.0",
  "author": "admin",
  "tags": ["python", "自动化", "测试"],
  "content": "## 触发条件\n\n用户要求执行自动化测试\n\n## 执行步骤\n\n1. 准备环境\n2. 运行测试\n3. 收集结果",
  "files": {
    "scripts/run.sh": "#!/bin/bash\necho \"Running tests...\"",
    "config/settings.json": "{\"timeout\": 30, \"retry\": 3}"
  }
}
```

### 成功响应（HTTP 200）

```json
{
  "ok": true,
  "message": "技能 'my-custom-skill' 导入成功",
  "path": "C:\\Users\\admin\\.hermes\\skills\\my-tools\\my-custom-skill"
}
```

### 失败响应（HTTP 400）

```json
{
  "ok": false,
  "message": "技能名称（name）不能为空"
}
```

```json
{
  "ok": false,
  "message": "技能名称（name）格式不正确。规则：只能包含小写字母、数字和连字符；必须以字母或数字开头和结尾；长度 1-64 字符"
}
```

```json
{
  "ok": false,
  "message": "技能内容（content）不能为空"
}
```

```json
{
  "ok": false,
  "message": "技能 'my-custom-skill' 已存在，请使用其他名称"
}
```

### 生成的文件结构

导入后，本地 `~/.hermes/skills/` 下将生成如下结构：

```
~/.hermes/skills/
  └── my-tools/                    ← category（有分类时）
      └── my-custom-skill/        ← name（slug）
          ├── SKILL.md            ← 由系统自动组装（YAML frontmatter + 传入的 content）
          ├── scripts/
          │   └── run.sh          ← 来自 files 参数
          └── config/
              └── settings.json   ← 来自 files 参数
```

若 `category` 为空（扁平结构），则 `my-custom-skill/` 直接挂在 `skills/` 根级：

```
~/.hermes/skills/
  └── my-custom-skill/
      └── SKILL.md
```

### 自动生成的 SKILL.md 格式

```yaml
---
name: "我的自定义技能"
description: "这是一个测试用的自定义技能"
visibility: personal
version: "1.0.0"
author: "admin"
tags: [python, 自动化, 测试]
---

## 触发条件

用户要求执行自动化测试

## 执行步骤

1. 准备环境
2. 运行测试
3. 收集结果
```

> 导入后，Hermes 下次会话启动时会自动加载该技能。可通过 `GET /api/skill-market/local` 立即验证。

---

## 8. 健康检查

- **Method**: `GET`
- **Path**: `/health`

### 调用示例

```http
GET /health
```

### 成功响应

```json
{
  "status": "ok",
  "service": "hermes-skill-market-api",
  "backend": "http://10.233.249.59:11899/api/v1"
}
```

---

## 9. 统一响应结构

所有接口（除下载代理和健康检查外）遵循统一响应格式：

```json
{
  "code": "0000",
  "message": "成功",
  "data": [...],
  "total": 0
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | `string` | 状态码。`"0000"` 表示成功 |
| `message` | `string` | 提示信息 |
| `data` | `array` | 技能数据列表 |
| `total` | `number` | 技能总数 |

### 安装/卸载接口响应格式（不同）

安装和卸载接口返回 `{"ok": true/false, "message": "..."}` 结构，通过 HTTP 状态码区分结果。

---

## 10. 技能数据模型

每个技能对象包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `string` | 技能唯一 ID（市场技能）。本地技能格式为 `local-{category}-{slug}` |
| `name` | `string` | 技能显示名称 |
| `slug` | `string` | 技能目录名（英文标识） |
| `namespaceId` | `string` | 命名空间 ID。本地技能固定为 `local` |
| `namespaceName` | `string` | 命名空间/分类名称（如 `self-hosted`） |
| `description` | `string` | 技能描述 |
| `visibility` | `string` | 可见性：`private`、`public`、`personal` |
| `status` | `string` | 状态：`active` |
| `currentVersion` | `string` | 当前版本号 |
| `latestVersion` | `string` | 最新版本号 |
| `lastVersionId` | `string` | 最新版本 ID（用于下载） |
| `downloadCount` | `number` | 下载次数 |
| `starCount` | `number` | 收藏数 |
| `ratingAvg` | `number` | 平均评分（0.0 - 5.0） |
| `ratingCount` | `number` | 评分人数 |
| `tags` | `array[string]` | 标签列表 |
| `createTime` | `string` | 创建时间（ISO 8601） |
| `updateTime` | `string` | 更新时间（ISO 8601） |
| `createNo` | `string` | 创建人账号 |
| `_source` | `string` | 数据来源（仅本地技能有此值，为 `"local"`） |

---

## 前端对接示例（Fetch API）

```javascript
const BASE = 'http://127.0.0.1:8643/api/skill-market';

// 1. 查询市场技能
async function getMarketSkills(installed = null) {
  const url = installed !== null
    ? `${BASE}/list?installed=${installed}`
    : `${BASE}/list`;
  const res = await fetch(url);
  return res.json();
}

// 2. 查询本地技能
async function getLocalSkills(visibility = null) {
  const url = visibility
    ? `${BASE}/local?visibility=${visibility}`
    : `${BASE}/local`;
  const res = await fetch(url);
  return res.json();
}

// 3. 安装技能
async function installSkill(skillId, versionId, version) {
  const res = await fetch(`${BASE}/install`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ skillId, versionId, version }),
  });
  return res.json();
}

// 4. 卸载技能
async function uninstallSkill(slug) {
  const res = await fetch(`${BASE}/uninstall`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slug }),
  });
  return res.json();
}

// 5. 下载 ZIP（浏览器直接触发）
function downloadZip(skillId, versionId) {
  window.location.href = `${BASE}/skills/${skillId}/versions/${versionId}/download`;
}
```

---

## CORS 说明

服务端已启用 CORS，允许所有来源（`*`）的 `GET`、`POST`、`OPTIONS` 请求，支持跨域前端调用。

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
```

---

## 配置说明

服务启动时从项目根目录的 `hub_config.yaml` 读取后端配置：

```yaml
skillhub:
  base_url: "http://10.233.249.59:11899/api/v1"
  username: "admin"
  password: "your-password"
```

- **有密码**：使用 `username + password` 调用 `/auth/local/login` 获取认证 Cookie/Token
- **无密码**：使用 Mock 模式，发送 `X-Mock-User-Id` 请求头

---

## 接口总览

| # | Method | Path | 说明 |
|---|--------|------|------|
| 1 | `GET` | `/api/skill-market/list` | 查询市场技能（支持 installed/visibility 过滤） |
| 2 | `GET` | `/api/skill-market/local` | 查询本地已安装技能 |
| 3 | `GET` | `/api/skill-market/local/{slug}/detail` | 查询本地技能详情（文件结构 + 文件内容） |
| 4 | `GET` | `/api/skill-market/skills/{id}/versions/{ver}/download` | 代理下载技能 ZIP |
| 5 | `POST` | `/api/skill-market/install` | 安装技能（从市场下载并安装到本地） |
| 6 | `POST` | `/api/skill-market/uninstall` | 卸载技能（从本地删除） |
| 7 | `POST` | `/api/skill-market/import-local` | 导入个人技能（本地创建/导入） |
| 8 | `GET` | `/health` | 健康检查 |