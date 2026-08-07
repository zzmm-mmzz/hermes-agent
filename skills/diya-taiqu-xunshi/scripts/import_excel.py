# -*- coding:utf-8 -*-
"""
低压台区巡视 Excel 文件校验工具。
检查列完整性、数据完整性、格式正确性。
"""
from pathlib import Path
import sys
from .utils import *


def get_next_week_range():
    """计算下周的周一~周日范围，返回 (start_date, end_date) 字符串"""
    today = datetime.now()
    # 周一 = 0, 周日 = 6
    days_ahead = 7 - today.weekday()  # 下周一距离今天的天数
    next_monday = today + timedelta(days=days_ahead)
    next_sunday = next_monday + timedelta(days=6)
    start_str = next_monday.strftime('%Y/%m/%d')
    end_str = next_sunday.strftime('%Y/%m/%d')
    return start_str, end_str


def find_excel_file():
    """查找最新匹配的低压台区巡视Excel文件"""
    xlsx_dir = Path("./低压台区巡视/")
    xlsx_files = list(xlsx_dir.glob(f"低压台区巡视计划数据-{datetime.now().year}*.xlsx"))
    if not xlsx_files:
        print("错误：未找到匹配的 低压台区巡视计划数据 文件")
        return None
    xlsx_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return xlsx_files[0]


def validate_columns(df_raw, required_cols):
    """校验列是否存在"""
    actual_cols = list(df_raw.columns)
    missing_cols = [c for c in required_cols if c not in actual_cols]
    if missing_cols:
        print(f"错误：缺少列 {missing_cols}，请补充完整")
        return False
    return True


def validate_data_completeness(df_data):
    """校验数据完整性：序号非空的行，台区名称和巡视子类必须非空"""
    errors = []
    for idx, row in df_data.iterrows():
        if pd.isna(row['序号']):
            continue
        if pd.isna(row['台区名称']) or pd.isna(row['巡视子类']):
            errors.append(f"第{idx+2}行缺少值：台区名称/巡视子类")
    return errors


def validate_data_format(df_valid):
    """校验数据格式（仅校验序号列）"""
    format_errors = []

    # 序号列格式校验
    for idx, val in df_valid['序号'].items():
        try:
            num = int(val)
            if num < 1:
                format_errors.append(f'第{idx+2}行「序号」值 "{val}" 格式错误')
        except (ValueError, TypeError):
            format_errors.append(f'第{idx+2}行「序号」值 "{val}" 格式错误')

    return format_errors


def find_valid_data_start(df_data):
    """
    从最后一行向上回溯，找到「配网工单编号」、「营销工单编号」
    两列不同时为空的最后一行，返回其下一行的索引作为有效数据的起始行。
    """
    business_cols = ['配网工单编号', '营销工单编号']
    # 从下往上遍历
    for i in range(len(df_data) - 1, -1, -1):
        row = df_data.iloc[i]
        # 两列中任意一列非空即视为有业务数据
        has_any = any(pd.notna(row[c]) for c in business_cols)
        if has_any:
            return i + 1  # 从下一行开始为有效数据
    return 0  # 没找到任何业务行，从头开始


def main(**kwargs):
    """主流程：读取并校验Excel数据"""
    # 1. 查找文件
    filename = find_excel_file()
    if filename is None:
        sys.exit(1)
    print(f"已找到匹配的 {filename} 文件")

    # 2. 读取原始数据
    df_raw = pd.read_excel(filename, header=None)
    header_row_idx = 0
    df_raw.columns = df_raw.iloc[header_row_idx].tolist()
    df_raw = df_raw.drop(header_row_idx).reset_index(drop=True)

    # 3. 校验列
    required_cols = ['序号', '配网工单编号', '营销工单编号', '台区编号', '台区名称', '所属线路', '电能表总数', '台区经理', '工单创建日期', '巡视日期', '巡视子类']
    if not validate_columns(df_raw, required_cols):
        sys.exit(1)

    # 4. 提取并过滤示例行
    df = df_raw[required_cols]
    df_data = df[~df['序号'].astype(str).str.contains('示例', na=False)].copy()

    # 4.1 筛选下周的巡视日期
    start_str, end_str = get_next_week_range()
    print(f"筛选下周巡视日期范围：{start_str} ~ {end_str}")
    # 将巡视日期统一转为日期对象进行比较
    df_data['巡视日期'] = pd.to_datetime(df_data['巡视日期'], errors='coerce')
    next_week_start = pd.to_datetime(start_str)
    next_week_end = pd.to_datetime(end_str)
    df_data = df_data[
        (df_data['巡视日期'] >= next_week_start) & (df_data['巡视日期'] <= next_week_end)
    ].copy()

    # 5. 确定有效数据起始行
    start_idx = find_valid_data_start(df_data)
    df_candidate = df_data.iloc[start_idx:].copy()
    if len(df_candidate) == 0:
        print("数据校验不通过，暂无有效数据")
        sys.exit(1)

    # 6. 精简列：保留序号、台区名称（巡视子类后续单独输出）
    output_cols = ['序号', '台区编号', '台区名称', '所属线路', '电能表总数', '台区经理', '巡视日期', '巡视子类']
    df_candidate = df_candidate[output_cols]

    # 7. 校验数据完整性
    completeness_errors = validate_data_completeness(df_candidate)
    if completeness_errors:
        print("数据校验失败，以下行存在空值，请将必要信息补充完整：")
        for e in completeness_errors:
            print(f"  {e}")
        sys.exit(1)

    # 8. 获取有效行
    df_valid = df_candidate[
        df_candidate['台区名称'].notna() & df_candidate['巡视子类'].notna()
    ].copy()
    valid_count = len(df_valid)
    if valid_count == 0:
        print("数据校验不通过，暂无有效数据，请将必要信息补充完整")
        sys.exit(1)

    # 9. 校验数据格式
    format_errors = validate_data_format(df_valid)
    if format_errors:
        print("数据格式校验失败，请修改：")
        for e in format_errors:
            print(f"  {e}")
        sys.exit(1)

    # 10. 通过
    print(f"全部校验通过，共 {valid_count} 行有效数据")
    # 输出序号、台区名称列
    # print(df_valid[['序号', '台区名称']].to_string(index=False))
    print(df_valid.to_string(index=False))
    # 单独输出第一行的巡视子类
    # first_subtype = df_valid['巡视子类'].iloc[0]
    # print(f"巡视子类：{first_subtype}")

    # ---- 新增：生成巡视清单文件 ----
    df_export = df_valid.copy()
    today_str = datetime.now().strftime('%Y/%m/%d')
    # 在台区经理列之后插入工单创建日期列
    cols = list(df_export.columns)
    manager_idx = cols.index('台区经理')
    cols.insert(manager_idx + 1, '工单创建日期')
    df_export['工单创建日期'] = today_str
    df_export = df_export[cols]

    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    export_path = f'低压台区巡视清单-{ts}.xlsx'
    df_export.to_excel(export_path, index=False)
    # print(f"已生成巡视清单文件：{export_path}")


if __name__ == '__main__':
    main()
