---
name: "Excel 表格处理"
description: "使用 pandas 处理 Excel 文件：筛选行、选择列、修改单元格值。"
category: data-science
---

# Trigger
- User needs to read an Excel file, filter rows based on conditions, select specific columns, modify cell values, and save the result.
- Tasks involving data cleaning, transformation, or extraction from Excel spreadsheets.
- excel 数据筛选
- **任何涉及 Excel 文件筛选行、选择列、修改单元格值、新增计算列的操作，都必须使用本技能目录下的 `process_excel.py` 中的 `process_excel()` 函数**

## 文件结构

```
skills/excel-pandas-processing/
├── SKILL.md
└── process_excel.py      # 可重用的 Excel 处理函数
```

## 强制要求

在处理任何 Excel 文件筛选/修改/删除等操作时，**必须按以下方式调用**：

```python
import sys
sys.path.insert(0, r"C:\.hermes\skills\excel-pandas-processing")
from process_excel import process_excel

df = process_excel(
    input_path="...",
    output_path="...",
    sheet_name=0,
    filter_conditions=None,    # 字符串 query 或字典等值筛选
    columns_to_keep=None,      # 保留的列列表
    columns_to_drop=None,      # 删除的列列表
    cell_modifications=None,   # [(条件字典, 列名, 新值), ...]
    new_columns=None,          # {'新列名': '计算公式', ...}
    index=False,
    inplace=False,             # True: 使用临时文件写入后替换原文件
    row_indices=None           # int/list/slice: 按行号筛选
)
```

## Steps

### 1. Use the process_excel function

Instead of hardcoding values, use the `process_excel()` function from `process_excel.py` with parameters for:
- Input/output file paths
- Sheet name/index
- Filter conditions
- Column selection/dropping
- Cell modifications
- New column calculations

### 2. 数据修改后必须展示更新后的完整表格（markdown格式）

**重要：** 修改完成后必须立即展示更新后的完整表格（markdown格式），不能只告知"已修改完成"而不展示数据。

### 3. 数据展示必须使用原始字段名

**重要：** 展示数据时必须使用 Excel 中的原始字段名，不得自行翻译或改写。

### 4. 修改前必须先备份原文件

**重要：** 在对文件进行筛选/修改/删除前，先备份原数据文件，然后对备份之外的副本进行操作。

#### Generic function template:
```python
import pandas as pd

def process_excel(
    input_path,
    output_path,
    sheet_name=0,
    filter_conditions=None,
    columns_to_keep=None,
    columns_to_drop=None,
    cell_modifications=None,
    new_columns=None,
    index=False
):
    """
    Process Excel file with configurable parameters.

    Args:
        input_path (str): Path to input Excel file
        output_path (str): Path to output Excel file
        sheet_name: Sheet name or index (default: 0)
        filter_conditions: Either:
                            - Dict: {'col': value} for equality filters
                            - Str: query string for pandas.query()
        columns_to_keep (list): Column names to keep (others dropped)
        columns_to_drop (list): Column names to drop
        cell_modifications (list): Tuples of (condition_dict, column, value)
                                    condition_dict: {'col': value} for equality
        new_columns (dict): {'new_col': 'formula_string'} for calculated columns
        index (bool): Whether to write DataFrame index to Excel

    Returns:
        pd.DataFrame: Processed DataFrame
    """

    # 1. Read Excel file
    df = pd.read_excel(input_path, sheet_name=sheet_name)

    # 2. Apply filters
    if filter_conditions:
        if isinstance(filter_conditions, str):
            df = df.query(filter_conditions)
        elif isinstance(filter_conditions, dict):
            mask = pd.Series(True, index=df.index)
            for col, val in filter_conditions.items():
                if col in df.columns:
                    mask &= (df[col] == val)
            df = df[mask]

    # 3. Column selection/dropping
    if columns_to_keep is not None:
        available = [c for c in columns_to_keep if c in df.columns]
        df = df[available]
    elif columns_to_drop is not None:
        drop_cols = [c for c in columns_to_drop if c in df.columns]
        df = df.drop(columns=drop_cols)

    # 4. Cell modifications
    if cell_modifications:
        for condition_dict, column, value in cell_modifications:
            if column in df.columns:
                mask = pd.Series(True, index=df.index)
                for col, val in condition_dict.items():
                    if col in df.columns:
                        mask &= (df[col] == val)
                df.loc[mask, column] = value

    # 5. Add new columns
    if new_columns:
        for col_name, formula in new_columns.items():
            try:
                df[col_name] = df.eval(formula)
            except Exception:
                df[col_name] = df.apply(
                    lambda row: eval(formula, {}, row.to_dict()), axis=1
                )

    # 6. Save result
    df.to_excel(output_path, index=index)
    return df

# Example usage:
if __name__ == "__main__":
    # Example 1: Filter Tech employees with salary > 7000
    process_excel(
        input_path='sales.xlsx',
        output_path='sales_processed.xlsx',
        sheet_name='Q1',
        filter_conditions="Amount > 1000 and Region == 'North'",
        columns_to_drop=['Timestamp', 'InternalID'],
        cell_modifications=[
            ({'Status': 'Pending'}, 'Status', 'Processing'),
            ({'Priority': 'Low'}, 'Priority', 'Medium')
        ],
        new_columns={
            'Tax': 'Amount * 0.13',
            'NetAmount': 'Amount - Tax',
        }
    )

```
