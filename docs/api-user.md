# 用户登录 API

用于 Hermes Desktop 的浏览器登录流程。在外部系统登录成功后，通过跳转将用户信息和票据保存到本地网关，后续可通过查询接口获取。

数据持久化在 `~/.hermes/user_data.json` 文件中，**网关重启时自动清除**，用户需要重新登录。

---

## POST /api/user/save

保存用户信息和登录票据。

### 请求格式

`Content-Type: application/json`

字段不限，根据实际需要传入。示例：

```json
{
  "username": "张三",
  "ticket": "abc123xyz789",
  "avatar": "https://example.com/avatar.png",
  "phone": "13800138000",
  "department": "信息中心",
  "role": "admin"
}
```

### 示例

```bash
curl -X POST http://127.0.0.1:8642/api/user/save \
  -H "Content-Type: application/json" \
  -d '{"username": "张三", "ticket": "abc123xyz"}'
```

### 响应

```json
{
  "success": true,
  "message": "User info saved"
}
```

### 错误响应

| 状态码 | 说明 |
|--------|------|
| 400 | 请求体为空或 JSON 格式错误 |
| 500 | 服务端写入失败 |

---

## GET /api/user

获取已保存的用户信息和登录票据。

### 示例

```bash
curl http://127.0.0.1:8642/api/user
```

### 响应（有数据）

```json
{
  "success": true,
  "data": {
    "username": "张三",
    "ticket": "abc123xyz789",
    "avatar": "https://example.com/avatar.png",
    "phone": "13800138000",
    "department": "信息中心",
    "role": "admin"
  }
}
```

### 响应（无数据）

```json
{
  "success": false,
  "error": "No user data found. Please login first."
}
```

状态码：**404**

---

## POST /api/user/logout

清除用户信息和登录票据。

### 示例

```bash
curl -X POST http://127.0.0.1:8642/api/user/logout
```

### 响应

```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

---

## 前端 JavaScript 调用示例

```javascript
// 1. 登录成功后保存用户信息
fetch('http://127.0.0.1:8642/api/user/save', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: '张三',
    ticket: 'abc123xyz',
    role: 'admin'
  })
})

// 2. 获取用户信息
const res = await fetch('http://127.0.0.1:8642/api/user')
const data = await res.json()
if (data.success) {
  console.log('当前用户:', data.data.username)
} else {
  // 未登录，跳转登录页
}

// 3. 退出登录
fetch('http://127.0.0.1:8642/api/user/logout', { method: 'POST' })
```

---

## 行为说明

| 场景 | 行为 |
|------|------|
| 网关启动 | 自动删除 `user_data.json`，需重新登录 |
| 保存数据 | 覆盖写入，旧的用户信息会丢失 |
| 查询无数据 | 返回 404，前端应跳转登录页 |
| CORS | 三个接口均支持跨域，浏览器可直接调用 |
| 存储路径 | `~/.hermes/user_data.json`（JSON 格式，UTF-8 编码） |
