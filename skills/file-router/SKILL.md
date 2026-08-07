---
name: "文件路由中枢"
description: "文件路由中枢。当用户上传文件并说\"处理\"、\"/process\"、\"帮我处理\"、\"执行技能\"时，自动根据文件名匹配对应的处理技能并调用。不做文件内容读取，只做路由分发。"
---

# 文件路由

## Trigger
- 用户说"处理这个文件"
- 用户说"/process"
- 用户说"执行这个文件对应的技能"
- 用户说"帮我处理"

## Instructions
1. 从用户消息中提取文件名（如：电话号码核实-2026.xlsx）
2. 运行路由脚本查找匹配技能：`python C:/.hermes/skills/file-router/router.py "文件名"`
3. 如果脚本返回技能名，直接调用该技能：`/{skill_name} 文件：{文件路径}`
4. 如果脚本返回 `no-match`，列出所有已安装技能供用户选择
5. 禁止直接读取文件内容复述给用户

## 示例
用户上传：电话号码核实-2026.xlsx
用户说：/process

→ 运行 router.py → 返回 phone-verification
→ 自动执行：/phone-verification 文件：C:\...\电话号码核实-2026.xlsx