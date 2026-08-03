---
name: mailcli
description: "POP3/SMTP 邮件收发工具。当用户要求收发邮件时使用此工具。仅支持 POP3 收件（不支持 IMAP），"
version: 1.0.0
author: mailcli
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Email, POP3, SMTP, CLI, Communication]
prerequisites:
  commands: [mailcli]
---

# mailcli

邮件 CLI 工具，支持 POP3 收件和 SMTP 发件，统一 JSON 输出。

以下为 CLI 命令参考。

## 配置目录

固定路径：`C:\.config\mailcli\`

## 命令参考

### 初始化

```bash
mailcli init
```

### 列出邮件

```bash
mailcli list                    # 最新 20 封
mailcli list --page 2           # 第 2 页
mailcli list --new              # 只看未读
```

### 阅读邮件

```bash
mailcli read <uidl>
```

### 发送邮件

```bash
mailcli send --to xxx@qq.com --subject "主题" --body "内容"
mailcli send --to xxx@qq.com --subject "报告" --attach ./file.pdf
```

## 输出格式

```json
{
  "schema": "v1", "code": "OK",
  "data": { ... },
  "error": null
}
```

## 错误码

| code | 含义 |
|------|------|
| `ERR_CONFIG_MISSING` | 配置未初始化，执行 `mailcli init` |
| `ERR_ACCOUNT_NOT_FOUND` | 账号不存在，检查 `--account` |
| `ERR_AUTH_FAILED` | 认证失败，检查授权码 |
| `ERR_CONNECT_TIMEOUT` | 连接超时 |
| `ERR_MAIL_NOT_FOUND` | 邮件不存在 |
| `ERR_SEND_FAILED` | 发送失败 |
| `ERR_INVALID_PARAM` | 参数错误 |

## 注意事项

- 仅支持 POP3 收件，不支持 IMAP
- 不支持删除邮件
- `list` 不标记已读，`read` 才标记
- `list --new` 只显示未读，不标记已读
- 调试模式加 `--debug`