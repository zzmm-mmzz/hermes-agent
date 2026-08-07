---
name: "月结电费催收"
description: "月结电费催收全流程自动化：修改月结电费催收规则 → 完结。通过 Playwright 浏览器自动化脚本逐步执行。"
version: 3.0.0
author: Jonny
hide_runtime: true
platforms: [windows]
metadata:
  hermes:
    tags: [电费, 催收, 供电所, powerclaw, automation]
parameters:
  type: object
  required: []
  properties:
    mode:
      type: string
      description: playwright浏览器执行方式
---

# 月结电费催收全流程自动化

通过 Playwright 浏览器自动化脚本，完成实时电费催收全流程。操作内网供电系统，修改月结电费催收规则。
**重要** 技能描述中`禁止`出现`催费员`、`供电所`等
**重要** 技能描述中`禁止`出现`催费员`、`供电所`、`isc账号`、`用户名`等

## 前置条件

- Python 3.x 已安装
- Python 包：`playwright`, `lxml`, `pandas`, `openpyxl`, `pywin32`（安装在 Hermes Agent 虚拟环境中）
- Playwright 浏览器：`python -m playwright install chromium`
- Chrome 浏览器已安装
- 技能目录下的 `references/` 文件夹包含所有脚本

## 重要：从 Hermes Agent 会话执行时的注意事项

本技能在 `terminal(background=true)` 模式下通过 subprocess 调用脚本。关键的坑：

### 必须使用 Hermes 虚拟环境的 Python
```bash
which python
# 应输出 /c/.hermes/hermes-agent/venv/Scripts/python
python -c "import sys; print(sys.executable)"
```

## 文件结构

```
skills/dianfei-yuejie/
├── run.py                           # 入口包装脚本，按 --step "yuejie" 分发执行
├── SKILL.md                         # 技能描述文件
├── references/
│   ├── __init__.py                  # 包初始化
│   ├── yuejie.py                    # 月结电费催收规则修改模块
│   ├── utils.py                     # 通用工具模块
│   └── session-notes.md             # 会话执行笔记（步骤参数映射、文件生成行为）
```

## 执行流程

用户请求修改月结电费催收规则时，按顺序逐步执行以下步骤。每步执行前告知用户该步骤的操作说明以及标题，执行完成后以markdown格式输出控制台内容。月结电费催收全流程自动化：询问用户修改规则 → 修改月结电费规则 → 完结。通过 Playwright 浏览器自动化脚本逐步执行。


**注意：** 参数`mode` 1静默执行、0普通，默认1静默执行

**静默执行定义：** "静默执行"仅指浏览器不弹出窗口(`--mode 1`)，其余一切不变。每一步执行完成后必须主动读取并汇报控制台输出和生成的文件明细，不能等到所有步骤完成才汇总。

**路径约定：** 所有 bash 命令统一使用 `/c/.hermes/skills/dianfei-yuejie` 作为技能目录，不要硬编码用户名。如果技能目录路径不同，以实际路径为准。

**重要：**  交互过程中，尽可能使用`您`而不是`你`,语气中要处处体现礼貌和关系。
**重要：**  给用户返回数据的时候，禁止出现`脚本`、`账号`、`密码`、`催费员`等词语
**重要：**  给用户返回数据的时候，禁止出现`脚本`、`账号`、`密码`等词语

## 已知问题与应对策略

### Python 文件 Tab/空格混用缩进错误（TabError: inconsistent use of tabs and spaces in indentation）

在 `references/yuejie.py` 文件中，代码可能混用 Tab 和空格进行缩进，导致 Python 解释器报 `TabError`。这通常在文件编辑过程中产生。

**排查方法**：查看目标 Python 文件的第 116 行附近，检查是否存在 Tab 缩进（显示为 `\t`）。可用以下命令检查整个文件中的 Tab 字符：
```bash
grep -rn $'\t' references/yuejie.py
```

**修复方法**：将 Tab 缩进替换为对应层级的空格缩进。缩进应与上下文保持一致（该文件使用 4 空格 + 8 空格两级缩进）。修复后重新执行即可。

**预防**：在编辑 `references/` 下的 Python 文件时，建议编辑器设置为"使用空格代替 Tab"。

### Playwright 点击被拦截（可重试解决）

点击"触发时间"输入框时，若页面存在加载遮罩层或 Element-UI 的清除图标，Playwright 会报 `intercepts pointer events` 错误导致超时。这属于页面瞬时状态问题，通常重试即可解决。若首次执行失败，告知用户页面状态异常，建议重试。

## Red Lines

- 介绍技能的时候，禁止输出帐号等敏感信息
- 给用户返回数据的时候，不要出现执行脚本之类的，要用人性化的语言，如`我正在帮你执行相关任务，请稍等`
- 给用户返回数据的时候，如果没有要求，默认不要分析他的数据，也不要得出结论，比如不要出现`本次催费业务已全部完成，`之类的
- 如果用户对数据进行了筛选，询问用户是否对数据进行修改，如果涉及文件，先备份文件，然后对文件进行修改，将修改内容展示给用户，询问用户是否确认

### 1. 询问用户修改规则

直接向用户发问，由助手（Assistant）询问用户要修改的内容，不需要调用脚本或 tool。

提问模板：
```
请问您是要修改触发时间还是计划时限？例如：
> 1. 修改触发时间为每月2号0点
> 2. 修改计划时限为3天
```

### 2. 提取用户输入数据
**重要** 这一步执行完成后需要用户确认数据

依据用户回答input,提取`触发时间`和`计划时限`,如果月份和年份没有提供默认为当月，如果计划时限没有单位或者单位不是`天`或者`小时`，自动转化`数值`和`单位`,`数值`要求为整数，向下取整，且不能为0。
要求：
  `触发时间`格式为 `%Y-%m-%d %H:%M:%s`, 提取到的值存入变量 `dt`, 允许为空（None）
  `计划时限`格式为 xx天、或xx小时，提取到的数值部分存入变量`val`, 提取到的单位存入变量`unit` ,两个都允许为空(None)  
  如果未提取到`触发时间`和`计划时限`,直接跳到`### 1. 询问用户修改规则`，让用户重新输入

**用户确认数据`1 确认 0 取消`,模板如下，**：
```
修改触发时间为每月2号0点
修改计划时限为3天
烦请审阅数据，是否修改:
[ ] 1 确认
[ ] 0 取消
```

### 3. 修改月结电费催收规则

依据提取到的参数`dt`, `val`, `unit` 调用脚本执行

```bash
cd /c/.hermes/skills/dianfei-yuejie && /c/.hermes/hermes-agent/venv/Scripts/python.exe -B run.py --step "yuejie" -d "${dt}" -v "${val}" -n "${unit}" --mode ${mode}
```

## 注意事项
- **禁止** 修改和增加`py文件`
- **禁止** 修改`SKILL.md`文件

### 内网环境执行要点（用户偏好）

- **禁止执行环境/依赖检查**：内网无法访问外网 pypi.org，pip install 会因 DNS 解析失败卡住。用户反复强调不要检查依赖——直接执行脚本，缺少依赖由用户自行处理。
- **禁止请求主线操作者更改系统配置**：包括安装包、更新环境变量、修改系统设置等。不要让用户去操作他的终端环境。
- **禁止修改 references/ 目录下的 Python 脚本**，除非用户明确要求修改。