# MCP Core Indicators 数据源架构

## 核心架构：双数据源模型

server.py 中的指标数据来自两个独立源头，在响应查询时合并返回。

### 源1：INDICATOR_DEFS（硬编码字典）

**位置：** server.py 约 line 252-303

**特点：**
- Python 进程启动时在模块级别初始化
- 7 个内置指标硬编码在字典中
- 属于**进程内存数据**，不在任何外部文件中
- 每次服务重启都会从 server.py 源码重建

**内置指标列表：**

| code | name |
|------|------|
| 10029b | 台区实时停电数 |
| 10030 | 当日报修次数 |
| 10020 | 综合线损率 |
| 20016 | 低电压用户数 |
| 10012 | 实时负荷 |
| 10013 | 当日最大负荷 |
| 67851 | 安全运行天数 |

### 源2：indicators_data.json（本地文件）

**位置：** 项目根目录下的 `indicators_data.json`

**特点：**
- 持久化存储，独立于进程生命周期
- 存储通过 MCP 工具添加的自定义指标
- 启动时通过 `_load_custom_indicators()` 加载到 INDICATOR_DEFS 中（仅添加不在 INDICATOR_DEFS 中的 code）

### 合并逻辑（list_indicators）

```python
# 约 line 532-562
items = _load_indicators_data()  # 从文件加载
merged = {}
for item in items:
    merged[item["code"]] = item        # 文件数据优先
for code, defn in INDICATOR_DEFS.items():
    if code not in merged:
        merged[code] = {...}            # 补充内置指标
```

### 删除逻辑（delete_indicator）

```python
# 约 line 584-601
del INDICATOR_DEFS[code]                    # 从内存字典移除
INDICATOR_FOLLOWED.pop(code, None)           # 从关注表移除
items = _load_indicators_data()              # 从文件移除
items = [item for item in items if item.get("code") != code]
_save_indicators_data(items)
```

**关键限制：** 内置指标无法被永久删除。重启服务后 INDICATOR_DEFS 重建，内置指标全部恢复。

## 查询生命周期

```
list_indicators 请求
  |
  v
_load_indicators_data() → 读取 indicators_data.json (持久化存储)
  |
  v
合并 INDICATOR_DEFS (内存中的硬编码字典)
  |
  v
按 sortOrder 排序后返回
```

## test_indicator 查询生命周期

```
test_indicator(code) 请求
  |
  v
INDICATOR_DEFS.get(code) → 从内存字典查找定义
  |                        (如果找不到返回 "指标 XXXX 不存在")
  v
get_build_params(code, ctx) → 构造请求参数
  |
  v
发送 HTTP 请求 → 获取响应
  |
  v
parse_indicator_to_standard(code, data) → 标准化解析
  |
  v
返回 {value, unit, trend}
```

## 常见误解澄清

| 误解 | 事实 |
|------|------|
| 删除指标后重启就没了 | 内置指标重启后必然恢复，因为它们硬编码在 server.py 中 |
| 重启服务意味着完全重置 | 重启只重建 INDICATOR_DEFS 内存字典，indicators_data.json 不受影响 |
| 指标不见了就是出 bug | 可能是 isHide=true 过滤导致的（list_indicators 默认不返回隐藏指标） |

## 隐藏 vs 删除

- **删除（delete_indicator）：** 从 INDICATOR_DEFS 和 indicators_data.json 中移除。对内置指标无效（重启恢复）
- **隐藏（hide_indicator）：** 在 indicators_data.json 中设置 isHide=true，list_indicators 默认过滤。对任何指标永久有效
