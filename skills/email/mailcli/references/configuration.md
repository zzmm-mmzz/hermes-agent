# mailcli 配置参考

## 配置文件位置

固定路径：`C:\.config\mailcli\config.toml`

## 全量配置项

```toml
[accounts.default]

[accounts.default.auth]
method = "plain"              # 认证方式: plain | cmd | oauth2
username = "user@company.com" # 邮箱地址/用户名
secret = "******"             # 密码/授权码

[accounts.default.receive]
protocol = "pop3"             # 收件协议
host = "pop3.company.com"     # 收件服务器
port = 110                    # 端口: 110(plain) / 995(ssl)
security = "plain"            # plain | ssl | starttls
timeout = 30                  # 连接超时秒数

[accounts.default.send]
protocol = "smtp"             # 发件协议
host = "smtp.company.com"     # 发件服务器
port = 25                     # 端口: 25(plain) / 465(ssl) / 587(starttls)
security = "plain"            # plain | ssl | starttls
timeout = 30                  # 连接超时秒数
```

## 常见邮箱配置

### QQ 邮箱

```toml
[accounts.default]
[accounts.default.auth]
method = "plain"
username = "xxx@qq.com"
secret = "授权码"

[accounts.default.receive]
protocol = "pop3"
host = "pop.qq.com"     # 注意：不是 pop3.qq.com
port = 995
security = "ssl"
timeout = 30

[accounts.default.send]
protocol = "smtp"
host = "smtp.qq.com"
port = 465
security = "ssl"
timeout = 30
```

### 163 邮箱

```toml
[accounts.default]
[accounts.default.auth]
method = "plain"
username = "user@163.com"
secret = "授权码"

[accounts.default.receive]
protocol = "pop3"
host = "pop3.163.com"
port = 110
security = "plain"
timeout = 30

[accounts.default.send]
protocol = "smtp"
host = "smtp.163.com"
port = 25
security = "plain"
timeout = 30
```

### Gmail

```toml
[accounts.default]
[accounts.default.auth]
method = "plain"
username = "user@gmail.com"
secret = "应用专用密码"

[accounts.default.receive]
protocol = "pop3"
host = "pop3.gmail.com"
port = 995
security = "ssl"
timeout = 30

[accounts.default.send]
protocol = "smtp"
host = "smtp.gmail.com"
port = 587
security = "starttls"
timeout = 30
```