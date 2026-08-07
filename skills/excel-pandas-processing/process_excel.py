"""
Excel 文件处理工具 - 可重用的通用函数

支持：按条件筛选行、选择/删除列、修改单元格值、新增计算列
"""

import os
import pandas as pd


def process_excel(
    input_path,
    output_path=None,
    sheet_name=0,
    filter_conditions=None,
    columns_to_keep=None,
    columns_to_drop=None,
    cell_modifications=None,
    new_columns=None,
    index=False,
    inplace=False,
    row_indices=None
):
    """
    Process Excel file with configurable parameters.

    Args:
        input_path (str): Path to input Excel file
        output_path (str, optional): Path to output Excel file. If None, uses input_path (in-place).
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
        inplace (bool): If True and overwriting input file, use temp file then rename
        row_indices (int, list, or slice): Row index or indices to keep. If int, keeps single row.
                                           If list, keeps those rows. If slice, uses .iloc[s].

    Returns:
        pd.DataFrame: Processed DataFrame
    """

    # 规范化路径：将 Unix 风格的 /c/ 等转换为 Windows 风格 C:\
    def _norm_path(p):
        if not p:
            return p
        p = p.strip()
        if p.startswith('/') and len(p) > 2 and p[2] == '/':
            # /c/path/to/file -> C:\path\to\file
            drive = p[1].upper() + ':'
            return drive + p[2:].replace('/', '\\')
        return p

    input_path = _norm_path(input_path)
    output_path = _norm_path(output_path) if output_path else None
    if output_path is None:
        output_path = input_path

    # 1. Read Excel file
    df = pd.read_excel(input_path, sheet_name=sheet_name)

    # 1a. Row index selection (applied before other filters)
    if row_indices is not None:
        if isinstance(row_indices, int):
            df = df.iloc[[row_indices]]
        elif isinstance(row_indices, (list, tuple)):
            df = df.iloc[row_indices]
        elif isinstance(row_indices, slice):
            df = df.iloc[row_indices]
        else:
            raise TypeError(f"row_indices must be int, list, tuple, or slice, got {type(row_indices)}")

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
    if inplace:
        import tempfile, os
        # Write to a temporary file first, then replace original
        tmp = tempfile.NamedTemporaryFile(
            suffix=os.path.splitext(input_path)[1] or '.xlsx',
            delete=False, dir=os.path.dirname(input_path) or '.'
        )
        tmp_path = tmp.name
        tmp.close()
        df.to_excel(tmp_path, index=index)
        os.replace(tmp_path, input_path)
        return df
    else:
        df.to_excel(output_path, index=index)
        return df


if __name__ == "__main__":
    # Example usage:
    # Filter rows with specific conditions, drop unneeded columns,
    # modify cell values, and add calculated columns.
    df = process_excel(
        input_path='待建工单.xlsx',
        output_path='待建工单_处理结果.xlsx',
        sheet_name=0,
        filter_conditions="序号 > 0",
        columns_to_drop=[],
        cell_modifications=[],
        new_columns={}
    )
    print(f"处理完成，共 {len(df)} 行数据")
    print(df.to_string())
