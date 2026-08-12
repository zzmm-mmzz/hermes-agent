---
name: mcp-core-indicator-add
description: '核心指标添加全流程：询问指标信息 → 本地查重 → 修改server.py → 重启服务 → 验证指标。注意：skip for 删除核心指标、修改指标配置'
version: 1.0.0
author: Powerclaw
hide_runtime: true
platforms: [windows]
metadata:
  hermes:
    tags: [核心指标, mcp, powerclaw, automation, core-indicators]
---

# 核心指标添加自动化

通过交互式对话，帮助用户向 MCP Core Indicators 服务添加新的核心指标。全流程：询问指标信息 → 本地查重 → 修改 server.py → 重启服务 → 验证指标。

## 前置条件

- 项目路径：`C:\.hermes\project\mcp-core-indicators\`
- 文件格式：`server.py` 是 MCP 服务主文件，`indicators_data.json` 是本地指标数据文件

## 执行流程

按顺序逐步执行以下步骤，每步输出进度。

**重要：** 交互过程中，使用 `您` 而不是 `你`，语气中处处体现礼貌和关系。
**重要：** 给用户返回数据时，禁止出现 `脚本`、`账号`、`密码` 等词语。

### 步骤1：询问核心指标信息

向用户逐一询问以下信息，每次询问一个，等用户回复后再问下一个：

#### 1.1 核心指标的名称和code

询问用户核心指标的名称和code（编码）。

- 如果用户提供了code，直接使用用户提供的code
- 如果用户没有提供code，用 Python 生成一个随机整数作为code（随机范围 50001-99999）

**重要：** 无论code是用户提供还是随机生成，都必须执行本地查重逻辑（步骤1.2-1.3）
**重要：** 调用前先打印进度信息

进度模板：
```
> progress: 步骤 1.1/6 — 询问核心指标名称和编码
```

#### 1.2 本地查重

获取用户的名称和code后，在本地查询是否有类似的核心指标：

1. 读取 `indicators_data.json` 文件，获取所有已注册指标列表
2. 读取 `server.py` 中的 `INDICATOR_DEFS` 注册表，获取所有内置指标
3. 按名称模糊匹配（名称包含用户输入关键词或用户输入关键词包含在已存在名称中）
4. 按code精确匹配

查询命令：
```bash
cd /c/.hermes/project/mcp-core-indicators && python -c "
import json
name_query = '{{用户输入的指标名称}}'
code_query = '{{用户提供的code或'None'}}'

# 读取本地指标文件
try:
    with open('indicators_data.json', 'r', encoding='utf-8') as f:
        items = json.load(f)
except:
    items = []

# 读取 server.py 中的 INDICATOR_DEFS
import re
with open('server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 提取 INDICATOR_DEFS 中的 name
names_in_defs = re.findall(r'\"(\\w+)\":\\s*\\{[^}]*\"name\":\\s*\"([^\"]+)\"', content)
print('=== 本地指标列表 ===')
for code, name in names_in_defs:
    print(f'{code}: {name}')
print('=== 本地文件指标 ===')
for item in items:
    print(f'{item.get(\"code\")}: {item.get(\"name\")}')

print()
print('=== 模糊匹配结果 ===')
for code, name in names_in_defs:
    if name_query and (name_query.lower() in name.lower() or name.lower() in name_query.lower()):
        print(f'MATCH: {code}: {name}')
for item in items:
    n = item.get('name', '')
    if name_query and (name_query.lower() in n.lower() or n.lower() in name_query.lower()):
        print(f'MATCH: {item.get(\"code\")}: {n}')
"
```

#### 1.3 处理查重结果

- 如果有查询到**类似**的指标（按名称模糊匹配），列出来给用户看，询问用户：
  - `1` 修改已存在的指标
  - `2` 新增指标

- 如果有**完全相同的code**已存在，直接提示用户该code已被占用，请用户重新提供code，回到步骤1.1

- 如果用户选择修改已存在的指标，则：
  1. 确认用户要修改哪个指标（按code确认）
  2. 询问要修改的字段（名称、url、请求参数、响应解析、是否关注等）
  3. 执行对应修改（直接跳到步骤3修改 server.py 中对应的指标定义）
  4. 跳过后面的步骤2和指标添加逻辑

- 如果用户选择新增指标，或者没有查到类似的指标，继续后续步骤

**进度模板：**
```
> progress: 步骤 1.3/6 — 查重完成，处理查重结果
```

#### 1.4 询问URL

询问指标请求的 URL 路径，例如：`/plan/base/counts`。

- 如果用户提供的是完整 URL（以 http 开头），提取其中的路径部分
- 如果用户不输入，则默认为 None（即 `/plan/base/counts`）

#### 1.5 询问请求方式

询问请求方式是 GET 还是 POST。

- 如果 URL 为 None（默认 `/plan/base/counts`），则默认为 POST
- 如果用户指定了 URL，按用户指定的方式

#### 1.6 询问请求参数示例

让用户提供一个请求参数的示例 JSON，并说明每个参数是怎么取值的。

**进度模板：**
```
> progress: 步骤 1.6/6 — 收集请求参数信息
```

#### 1.7 询问响应数据示例

让用户提供一个响应数据的示例 JSON，并说明：

- 需要取的数值是哪个字段
- 单位是什么
- 趋势数值是怎么拼接的（如果有趋势）
- 如果没有趋势，就不要填写

**进度模板：**
```
> progress: 步骤 1.7/6 — 收集响应数据解析信息
```

#### 1.8 询问是否默认关注

询问用户：这个指标默认是否关注？

- 是：followed = True
- 否：followed = False

**进度模板：**
```
> progress: 步骤 1.8/6 — 确认关注状态
```

### 步骤2：确认信息并保存

在步骤1所有信息收齐后，汇总展示给用户确认：

```
核心指标信息确认：
- 名称：{{指标名称}}
- code：{{指标编码}}
- URL：{{url}}
- 请求方式：{{method}}
- 请求参数：{{json}}
- 取值字段：{{field}}
- 单位：{{unit}}
- 趋势：{{trend}}
- 默认关注：{{是/否}}

请确认以上信息是否正确：
[ ] 1 确认无误，开始添加
[ ] 0 取消
```

用户确认后，执行步骤3。

### 步骤3：修改 server.py

根据收集到的信息，修改 `server.py` 文件。

#### 3.1 添加 build_params 函数（如果需要）

如果指标使用了非默认的参数（需要额外的请求参数，如 `ds`、`dt`、`idx_no` 等），需要在 `server.py` 中添加一个 `_build_params_{code}` 函数。

如果参数与 `_build_params_default` 一致（标准参数 `code` + `org_lev`/`org_no`/`pageNum`/`pageSize`），则跳过此步，直接使用 `_build_params_default`。

如果参数与 `_build_params_common_counts` 一致（标准参数，code不同），则使用 `_build_params_common_counts`。

#### 3.2 添加或修改 INDICATOR_DEFS 注册表

向 `INDICATOR_DEFS` 字典中添加新的指标定义：

```python
"{code}": {{
    "name": "{指标名称}",
    "url": {url},  # None 表示 /plan/base/counts，否则为字符串路径
    "build_params": _build_params_{function_name},
    "parse_result": None,
    "sortOrder": {next_sort_order},
}},
```

`sortOrder` 取当前最大 sortOrder + 1。

#### 3.3 添加 parse_indicator_to_standard 解析逻辑

在 `parse_indicator_to_standard` 函数中添加该指标的特定解析逻辑（在 else 分支之前添加 elif 分支）：

```python
elif code == "{code}":
    # {指标名称}：根据用户提供的信息编写解析逻辑
    if not isinstance(inner_data, list) or len(inner_data) == 0:
        result["value"] = 0
        result["unit"] = "{unit}"
        return result
    first = inner_data[0]
    val = first.get("{value_field}")
    if val is not None:
        result["value"] = val
    result["unit"] = "{unit}"
    # 如果有趋势
    all_val = first.get("{trend_field}")
    if all_val is not None:
        result["trend"] = f"今日累计{all_val}个"
```

**解析逻辑编写指南：**

根据用户提供的响应示例和说明，编写合适的解析逻辑：

- **简单取值**：`inner_data[0].value` → 直接取第一个元素的value字段
- **累加**：遍历 `inner_data` 累加 `index_val`
- **嵌套对象**：如 `inner_data["rows"][0]["value"]`（类似综合线损率 10020）
- **直接取字段**：从 `inner_data` dict 中取特定字段

**如果用户没有提供特殊解析逻辑**，保留默认通用逻辑（`inner_data[0].value` + 通用单位）。

#### 3.4 更新 INDICATOR_FOLLOWED

如果指标默认关注，在 `INDICATOR_FOLLOWED` 字典中添加：
```python
"{code}": {true/false},
```

#### 3.5 更新 indicators_data.json

向 `indicators_data.json` 文件中添加新指标记录：

```python
{{
    "code": "{code}",
    "name": "{指标名称}",
    "url": {url},
    "isHide": false,
    "sortOrder": {next_sort_order}
}}
```

**进度模板：**
```
> progress: 步骤 3/5 — server.py 修改完成
```

### 步骤4：重启服务

重启 MCP Core Indicators 服务。

**重要：** 不要用复杂的 bash 管道组合命令（如 wmic + grep 混用），它们容易在 git-bash 中因引号嵌套导致语法错误。使用简单的分步命令。

**4.1 查找 server.py 进程**

先查所有 python.exe 进程：
```bash
tasklist //FI "IMAGENAME eq python.exe" //FO CSV //NH
```

观察输出，确认哪个是 server.py（注意：端口 8100 上监听的就是 server.py），记录对应的 PID。

**4.2 杀掉旧进程**

```bash
taskkill //F //PID <PID号>
```

确认提示"成功: 已终止 PID 为 xxx 的进程"。

**4.3 启动新服务**

使用 Hermes 的 `terminal(background=true)` 模式启动服务，不要用 nohup（会被 Hermes 工具规则拦截）：

```bash
cd /c/.hermes/project/mcp-core-indicators && python server.py
```

设置为 background=true 即可。

**4.4 验证服务是否启动成功**

等待 3-4 秒后，用 curl 验证服务可正常响应：

```bash
curl http://localhost:8100/ 2>/dev/null
```

预期返回 JSON 包含 server 信息和 endpoints。

**注意：**
- Hermes 的 background 模式下，Python stdout/stderr 可能不会立即显示在 process log 中，但这不代表服务有问题
- `curl` 是最可靠的验证方式
- 如果 curl 能正常拿到响应，说明服务已启动成功

**进度模板：**
```
> progress: 步骤 4/5 — 服务重启完成
```

### 步骤5：验证核心指标

通过 `test_indicator` 工具验证新添加的核心指标是否工作正常。

**方式一：curl（推荐，最可靠）**

```bash
curl -X POST http://localhost:8100/tools/indicators \
  -H "Content-Type: application/json" \
  -d '{"name":"test_indicator","arguments":{"login_name":"<login_name>","code":"<新指标code>"}}' 2>/dev/null
```

**方式二：Python urllib**

```bash
cd /c/.hermes/project/mcp-core-indicators && python -c "
import json
import urllib.request

body = json.dumps({
    'name': 'test_indicator',
    'arguments': {
        'login_name': '{{用户告知的login_name}}',
        'code': '{{新指标的code}}'
    }
}).encode('utf-8')

req = urllib.request.Request(
    'http://localhost:8100/tools/indicators',
    data=body,
    headers={'Content-Type': 'application/json'}
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        print(json.dumps(result, ensure_ascii=False, indent=2))
except Exception as e:
    print(f'Error: {e}')
"
```

**注意：** 验证前需要用户提供 login_name，如果用户未提供则先询问。
**注意：** 如果 Python urllib 脚本返回空输出（无任何打印内容），改用 curl 方式验证。这通常是因为 git-bash 下 Python 子进程 stdout 被缓冲或重定向导致的，并非服务问题。

验证结果分析：
- 如果返回的数据中有 `parsed_result.value` 且有数值，说明指标添加成功
- 如果返回 `error` 字段，说明指标存在问题，需要排查
- 如果返回 `"指标 XXXX 不存在"`，先检查服务是否为新进程（检查 PID 和启动时间），不要直接认定代码有问题——旧进程可能返回已过期的内存状态

**进度模板：**
```
> progress: 步骤 5/5 — 核心指标验证完成
```

### 步骤6：汇总结果

向用户汇报完整的添加结果：

```
核心指标添加完成：
- 名称：{{指标名称}}
- code：{{指标编码}}
- URL：{{url}}
- 请求方式：{{method}}
- 响应数据：{{value}} {{unit}}
- 默认关注：{{是/否}}
- 验证结果：成功/失败

推荐：
1. 继续添加下一个核心指标
2. 关闭当前会话 <- 执行指令 /stop
```

## 注意事项

- **禁止** 直接修改 server.py 的 `_build_params_default` 函数
- **禁止** 删除已有指标定义，只做新增
- **禁止** 修改 `SKILL.md` 文件
- 如果用户提供的信息不完整（如缺少请求参数说明），请用户补充
- 添加完成后务必验证指标是否正常工作
- 如果验证失败，向用户展示完整的请求和响应信息，帮助定位问题

## 故障排查

### 删除指标后重启服务，查询时仍出现

**症状：** 用户在界面上或通过 delete_indicator 工具删除了某个指标，重启 MCP 服务后，list_indicators 查询时该指标仍然出现。

**原因（架构理解关键）：** server.py 中有两套指标数据源：
1. **INDICATOR_DEFS**（硬编码字典，约 line 252-303）—— 模块加载时在 Python 进程内存中初始化，包含 7 个内置指标（10029b, 10030, 10020, 20016, 10012, 10013, 67851）
2. **indicators_data.json**（本地 JSON 文件）—— 存储通过工具添加的自定义指标

两套数据在 `list_indicators` 函数（约 line 532-562）中**合并返回**：
- 先用 `indicators_data.json` 的数据填充 merged dict
- 再用 `INDICATOR_DEFS` 补充不在 merged 中的码

这意味着：**即使 `indicators_data.json` 中已无该指标记录，只要它在 `INDICATOR_DEFS` 中硬编码存在，`list_indicators` 仍会返回它。**

具体来说：
- `delete_indicator` 工具（约 line 584-601）确实做了三件事：从 `INDICATOR_DEFS` 中 `del`、从 `INDICATOR_FOLLOWED` 中 `pop`、从 `indicators_data.json` 中移除
- 但 `_load_custom_indicators()` 只在**启动时**从文件加载**不在 `INDICATOR_DEFS` 中**的指标，不会删除
- **硬编码在 `INDICATOR_DEFS` 中的内置指标无法通过 `delete_indicator` 真正删除**——它只是从进程内存的字典中移除了该 key，重启服务后 `server.py` 重新加载，`INDICATOR_DEFS` 字典重建，内置指标全部恢复

**排查步骤：**
1. 确认当前服务进程 PID：`netstat -ano | findstr 8100`
2. 确认该进程是否是新启动的：`powershell -Command "Get-Process -Id <PID> | Select-Object Id,StartTime"`
3. 区分指标类型：
   - 内置指标（INDICATOR_DEFS 中硬编码的 7 个）—— 重启后必然恢复，无法永久删除
   - 自定义指标（通过工具添加，仅存在 indicators_data.json 中）—— 删除后重启不应出现

**解决方法：**
1. 如果是**内置指标**不想显示 → 使用 `hide_indicator` 工具设置 isHide=true（这会将 isHide 状态写入 indicators_data.json），`list_indicators` 默认过滤 isHide=true 的指标
2. 如果是**自定义指标**删除后仍出现 → 检查 `indicators_data.json` 中是否确实移除了该记录，然后确认杀掉的是正确的旧进程并重新启动了新进程。验证方法：杀掉旧进程后用 `curl http://localhost:8100/` 确认旧进程已停，然后用 `terminal(background=true) python server.py` 启动新进程

**验证方法：**
```bash
# 查看 list_indicators 返回的指标列表
curl -X POST http://localhost:8100/tools/indicators -H "Content-Type: application/json" -d '{"name":"list_indicators","arguments":{}}' 2>/dev/null

# 查看 indicators_data.json 中的记录（反映持久化的自定义指标）
cat /c/.hermes/project/mcp-core-indicators/indicators_data.json
```
如果 list_indicators 返回的指标数多于 indicators_data.json 中记录的指标数，多出来的就是硬编码在 INDICATOR_DEFS 中的内置指标。

### 调用 test_indicator 返回 "指标 XXXX 不存在"

**症状：** 代码中明明有 `INDICATOR_DEFS` 定义（如 10020 综合线损率），但服务端返回 `"指标 XXXX 不存在"`。

**原因：** 旧 server.py 进程虽然存活并监听端口 8100，但已经处于异常状态（进程卡死、内存数据损坏等），无法正常读取 `INDICATOR_DEFS` 或响应 JSON-RPC 请求。未重启过服务的情况下，服务可能运行了数小时或数天，进程状态逐渐劣化。

**排查步骤：**
1. 检查端口上有哪个进程：`netstat -ano | grep 8100` 或 `netstat -ano | findstr 8100`
2. 确认该 PID 是否是 server.py：`tasklist //FI "PID eq <PID>" //FO CSV //NH`
3. 用 curl 测试服务是否能正常响应：`curl http://localhost:8100/` 和 `curl -X POST http://localhost:8100/tools/indicators -H "Content-Type: application/json" -d '{"name":"test_indicator","arguments":{"login_name":"zhousj","code":"10020"}}'`

**修复方法：**
- 直接杀掉旧进程：`taskkill //F //PID <PID>`
- 用 `terminal(background=true)` 重新启动：`cd /c/.hermes/project/mcp-core-indicators && python server.py`
- 等 3-4 秒后用 curl 验证新进程是否正常响应
- **不需要修改 server.py 代码**——如果代码中有指标定义但返回不存在，100% 是进程问题

**验证方法（推荐 curl 而非 Python urllib）：**
在 git-bash 环境下，`python -c "..."` 方式的验证脚本有时不会输出任何内容（stdout 缓冲或重定向问题），而 `curl` 始终可靠。优先使用 curl 进行验证。

### Python 子进程不输出任何内容

**症状：** `execute_code` 或 `terminal` 中调用 Python 脚本，脚本内包含 `print()` 但输出显示为空。

**原因：** git-bash 环境下 Python 子进程的 stdout 可能被缓冲或重定向。尤其是在 `execute_code` 中调用 `from hermes_tools import terminal` 后再执行 Python 脚本时，输出可能被吞掉。

**解决方法：**
- 改用 `curl` 代替 Python urllib 进行 HTTP 测试
- 直接在 `terminal` 中运行 curl 命令，不要嵌套在 Python -c 中

## 已知问题

- 默认 `/plan/base/counts` 使用 POST 批量请求方式，新指标如果在同一URL下会被合并到批量请求中
- 如果使用自定义 URL，指标将单独请求
- test_indicator 工具需要服务在 8100 端口运行
