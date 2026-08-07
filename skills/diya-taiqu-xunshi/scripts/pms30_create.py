# -*- coding:utf-8 -*-
#import pandas as pd
from pathlib import Path
# from contextlib import ExitStack

# from playwright.sync_api import sync_playwright

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from .utils import *

# from datetime import datetime, timedelta


class Base():
    """低压台区巡视自动化"""

    def __init__(self):
        pass

    @step_wrapper
    def _login(self, page, step, flow):
        """登录配网微应用系统"""
        # page.goto("http://25.89.148.197/ds/app-pms-app-ds-patrol-pcui/patrolManage") #测试
        page.goto("http://25.212.187.127/ds/app-pms-app-ds-patrol-pcui/patrolManage") #生产
        page.get_by_role("textbox", name="请输入您的账号").click()
        page.get_by_role("textbox", name="请输入您的账号").fill(USERNAME3)
        page.get_by_role("textbox", name="请输入您的密码").click()
        page.get_by_role("textbox", name="请输入您的密码").fill(PASSWORD3)
        # print(PASSWORD3)
        page.get_by_role("link", name="立即登录").click()
        report(step, "已登录至配网数字化管控微应用", flow=flow)
        # remote_log("SELECT", "登录配网数字化管控微应用完成", batch_id=step)

    @step_wrapper
    def _open_new_work_order(self, page, step, flow):
        """进入巡视工单管理页面"""
        # 等待菜单自动展开
        page.wait_for_timeout(3000)
        if page.get_by_text("精益化运维").locator("../..").locator("li.el-submenu.is-opened").count() == 0:
            page.get_by_text("精益化运维").click()
        page.locator('ul[role=menubar] li[role=menuitem].el-submenu li.el-submenu div.menu-level-2').get_by_text('配网巡视管理').click()
        page.locator('ul[role=menubar] li[role=menuitem].el-submenu li.el-submenu div.menu-level-3').get_by_text('巡视工单管理').wait_for()
        page.locator('ul[role=menubar] li[role=menuitem].el-submenu li.el-submenu div.menu-level-3').get_by_text('巡视工单管理').click()
        report(step, "进入巡视工单管理页面", flow=flow)
        # remote_log("SELECT", "进入巡视工单管理页面", batch_id=step)

    def _load_patrol_plan_data(self):
        """加载最新生成的巡视计划数据"""
        try:
            xlsx_dir = Path("./")
            xlsx_files = list(xlsx_dir.glob("低压台区巡视清单-*.xlsx"))
            if not xlsx_files:
                print("错误：未找到匹配的 低压台区巡视清单.xlsx 文件")
                return None

            xlsx_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            filename = xlsx_files[0]

            xlsx_dir2 = Path("./低压台区巡视/")
            xlsx_files2 = list(xlsx_dir2.glob(f"低压台区巡视计划数据-{datetime.now().year}*.xlsx"))
            xlsx_files2.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            filename2 = xlsx_files2[0]

            df = pd.read_excel(filename)
            return df, filename, filename2
        except Exception as e:
            print(f"加载巡视计划数据失败: {e}")
            return None

    @staticmethod
    def _get_next_workday(days=3):
        """计算从今天起第N个工作日后的日期（跳过周末），返回 'YYYY-MM-DD 00:00' 格式字符串"""
        today = datetime.now()
        count = 0
        current = today
        while count < days:
            current += timedelta(days=1)
            if current.weekday() < 5:  # 周一=0 ... 周五=4
                count += 1
        return current.strftime("%Y-%m-%d 00:00")

    def _set_patrol_schedule_time(self, page, row_idx, total, step, flow):
        """设置计划结束时间"""
        try:
            date_str = self._get_next_workday(3)
            # date_str = "2026-07-20 00:00"
            page.locator("div.ds-detail-form-box").get_by_text("计划结束时间").locator("../..").get_by_role("textbox").fill(date_str)
            page.locator('div.el-picker-panel__footer button.is-plain span').get_by_text('确定', exact=True).click()

            if page.locator('div.el-form-item__error').count() > 0:
                print('计划结束时间不合规，使用缺省值："2028年1月1日"')
                page.locator("div.ds-detail-form-box").get_by_text("计划结束时间").locator("../..").get_by_role("textbox").fill("2028-01-01 00:00")
                page.locator('div.el-picker-panel__footer button.is-plain span').get_by_text('确定', exact=True).click()
            print(f"完成计划结束时间选择")
            report(step, f"完成计划结束时间选择", flow=flow)
            # page.wait_for_timeout(1000)
        except Exception as e:
            print(f"设置计划结束时间失败: {e}")
            report(step, f"设置计划结束时间失败: {e}", flow=flow)

    def _select_patrol_device(self, page, device_name, line_name, row_idx, total, step, flow):
        """选择巡视设备"""
        try:
            # page.get_by_text("低压").click()
            # page.locator("span.ds-search-card-large-category-type-t").get_by_text("低压").click()
            # page.get_by_text("台区", exact=True).click()
            # page.wait_for_timeout(2000)

            device_name_str = str(device_name).replace(" ", "").strip()
            line_name_str = str(line_name).replace(" ", "").strip()
            textbox = page.get_by_role("textbox", name="请输入站线名称 设备类型 电压等级 设备名称")
            textbox.click()
            textbox.fill(device_name_str)
            textbox.press("Enter")
            page.wait_for_timeout(3000)

            # 找不到巡视设备
            if page.locator('span.ds-noDataImg-nwz').count() > 0:
                print(f'第 {row_idx + 1} / {total} 条巡视设备 "{device_name}" 无法在系统中查询到，请核对后再次提交')
                report(step, f'第 {row_idx + 1} / {total} 条巡视设备 "{device_name}" 无法在系统中查询到，请核对后再次提交', flow=flow)
                return None

            # 展开巡视设备列表
            target = page.locator('div.ds-form-item div.ds-open')
            if target.count() > 0:
                target.click()
                page.wait_for_timeout(1000)

            # 选择搜到的所有低压设备
            found10kv = False
            has_non10kv = False
            found = False
            while True:
                els = page.locator("div.ds-form-tree.ds-form-tree-q div.ds-children div.ds-content").all()
                clicked = False
                for el in els:
                    text = (el.locator('div.ds-child-value').text_content() or '').strip()
                    if '交流10kV' in text:
                        found10kv = True
                        continue
                    has_non10kv = True
                    text2 = (el.locator('div.ds-child-content-text').text_content() or '').strip()
                    if line_name_str in text2:
                        el.click()
                        found = True
                        clicked = True
                        break

                if not clicked:
                    break

            if not found:
                if found10kv and not has_non10kv:
                    print(f'第 {row_idx + 1} / {total} 条巡视设备 "{device_name}" 的标签为"交流10kV"，无法选到低压设备，请核对后再次提交')
                    report(step, f'第 {row_idx + 1} / {total} 条巡视设备 "{device_name}" 的标签为"交流10kV"，无法选到低压设备，请核对后再次提交', flow=flow)
                else:
                    print(f'第 {row_idx + 1} / {total} 条巡视设备 "{device_name}" 的低压设备不属于该线路"{line_name_str}"，请核对后再次提交')
                    report(step, f'第 {row_idx + 1} / {total} 条巡视设备 "{device_name}" 的低压设备不属于该线路"{line_name_str}"，请核对后再次提交', flow=flow)
                return None

            print(f"完成巡视设备选择（第 {row_idx + 1} / {total} 条）")
            # report(step, f"完成巡视设备选择（第 {row_idx + 1} / {total} 条）", flow=flow)
            return device_name_str
        except Exception as e:
            print(f"选择巡视设备失败: {e}")
            report(step, f"选择巡视设备失败: {e}", flow=flow)
            return None

    def _select_patrol_type(self, page, patrol_type, row_idx, total, step, flow):
        """选择巡视子类"""
        try:
            page.locator("div:nth-child(2) > .content-value > .el-form-item > .el-form-item__content > .el-input > .el-input-group__append > .tongTuiIcon").click()
            all_type_tags_raw = page.locator('.ds-tag-box .ds-tag-button').all_text_contents()
            all_type_tags = [t.strip() for t in all_type_tags_raw if t.strip()]
            patrol_type = patrol_type.strip()
            if patrol_type not in all_type_tags:
                print(f'巡视子类 "{patrol_type}" 不匹配可选标签，选择缺省值"迎峰度夏"')
                report(step, f'巡视子类 "{patrol_type}" 不匹配可选标签，选择缺省值"迎峰度夏"', flow=flow)
                patrol_type = "迎峰度夏"
            page.locator('.ds-tag-box .ds-tag-button').get_by_text(patrol_type, exact=True).click()

            print(f"完成巡视子类选择")
            report(step, f"完成巡视子类选择", flow=flow)
        except Exception as e:
            print(f"选择巡视子类失败: {e}")
            report(step, f"选择巡视子类失败: {e}", flow=flow)

    def _select_others(self, page, row_idx, total, step, flow):
        """选择重要程度、巡视要求"""
        try:
            page.locator("div:nth-child(2) > .content-value > .el-form-item > .el-form-item__content > .el-input > .el-input-group__append > .tongTuiIcon").click()
            page.locator("div.ds-detail-form-box").get_by_text("重要程度").locator("../..").locator('div.el-form-item--small').click()
            page.locator("li.el-select-dropdown__item").get_by_text("一般").nth(1).click()

            page.locator("div.newmain-container-table div.el-table__fixed th.el-table-column--selection span.el-checkbox__inner").click()
            # 无头模式
            if page.locator("button.el-popover__reference").get_by_text("更多").count() > 0:
                page.locator("button.el-popover__reference").get_by_text("更多").click()
            page.get_by_text("批量操作").click()
            page.locator("div.ds-detail-form-item").get_by_text("巡视要求").locator("../..").locator('div.no-padding').click()
            page.locator("li.el-select-dropdown__item").get_by_text("必打卡必拍照", exact=True).last.click()
            page.get_by_text("修改全部项").click()

            print(f"完成重要程度、巡视要求选择")
            report(step, f"完成重要程度、巡视要求选择", flow=flow)
        except Exception as e:
            print(f"选择重要程度、巡视要求失败: {e}")
            report(step, f"选择重要程度、巡视要求失败: {e}", flow=flow)

    def _save_and_get_plan_number(self, page, row_idx, total, step, flow):
        """保存工单并获取工单编号"""
        try:
            # time.sleep(100000)
            page.get_by_role("button", name="确定").click()
            page.wait_for_timeout(5000)
            els = page.locator('div#pms-app-ds-patrol-pcui div#pms-app-ds-patrol-pcui div.el-table__header-wrapper+div tbody tr').all()  #   表记录
            result2 = ''
            if els:
                # 取最后一条
                el = els[0].locator('td.el-table_1_column_4 span span')
                result2 = el.text_content().strip()
            print(f"完成巡视计划创建，编号 {result2}")
            report(step, f"完成巡视计划创建，编号 {result2}", flow=flow)
            if result2:
                remote_log("CREATE", "巡视计划创建完成", batch_id=step, workst_no=result2, workst_tp='低压台区巡视-配网微应用')
            return result2
        except Exception as e:
            print(f"保存工单失败: {e}")
            report(step, f"保存工单失败: {e}", flow=flow)
            return None

    @step_wrapper
    def _create_patrol_plans(self, page, step, flow):
        """创建巡视计划（所有行共用同一个工单）"""
        data = self._load_patrol_plan_data()
        if data is None:
            return
        df, filename, filename2 = data

        plan_numbers = []

        # 1. 点击"新增"按钮创建一个工单
        page.locator('div#pms-app-ds-patrol-pcui div#pms-app-ds-patrol-pcui div.ds-table-actions-wrap span').get_by_text('新增').click()

        # 2. 设置计划结束时间（只一次）
        self._set_patrol_schedule_time(page, 0, len(df), step=step, flow=flow)

        # 3. 循环选择所有巡视设备（不点确认，只逐个勾选）
        page.locator("span.ds-search-card-large-category-type-t").get_by_text("低压").click()
        page.get_by_text("台区", exact=True).click()
        page.wait_for_timeout(2000)
        for row_idx, row in df.iterrows():
            device_name = row['台区名称']
            patrol_type = row['巡视子类']
            line_name = row['所属线路']

            # if pd.isna(device_name) or pd.isna(patrol_type):
            #     print(f"警告：第 {row_idx + 1} / {len(df)} 条数据不完整，跳过")
            #     report(step+1, f"警告：第 {row_idx + 1} / {len(df)} 条数据不完整，跳过", flow=flow)
            #     continue

            print(f"--- 选择设备 第 {row_idx + 1} / {len(df)} 条：{device_name}（{line_name}） ---")
            report(step+1, f"选择设备 第 {row_idx + 1} / {len(df)} 条：{device_name}（{line_name}）", flow=flow)

            device_name_str = self._select_patrol_device(page, device_name, line_name, row_idx, len(df), step=step+1, flow=flow)
            if device_name_str is not None:
                plan_numbers.append({"row": row_idx + 1, "device": device_name_str, "number": ""})

        # 4. 所有设备选完后，点击确认按钮提交
        if plan_numbers:
            page.page.evaluate("document.querySelector('div.ds-confirm-quantity-btn').click()")
            page.wait_for_timeout(2000)
        else:
            print("未能选择任何巡视设备")
            report(step+1, "未能选择任何巡视设备", flow=flow)
            return

        # 5. 更改工单名称
        # title = page.locator("div.title span").get_by_text("所属线路").locator("../..").locator("div.el-tooltip").text_content().strip()
        # page.locator("div.title span").get_by_text("工单名称").locator("../..").locator("input").fill(f"{title}-低压台区巡视计划")

        # 6. 选择巡视子类，取第一条有效数据的巡视子类
        first_patrol_type = None
        for _, row in df.iterrows():
            patrol_type = row['巡视子类']
            if not pd.isna(patrol_type):
                first_patrol_type = patrol_type
                break
        if first_patrol_type:
            self._select_patrol_type(page, first_patrol_type, 0, len(df), step=step+2, flow=flow)

        # 7. 选择重要程度、巡视要求
        self._select_others(page, 0, len(df), step=step+3, flow=flow)

        # 8. 保存一次，获取工单编号
        result2 = self._save_and_get_plan_number(page, 0, len(df), step=step+4, flow=flow)
        if result2:
            for pn in plan_numbers:
                pn["number"] = result2

        # 汇总报告
        if plan_numbers:
            # summary = ", ".join([f"原第{p['row']}条: {p['number']}" for p in plan_numbers])
            # # print(f"全部创建完成，共 {len(plan_numbers)} 条巡视计划：{summary}")
            # print(f"全部创建完成，巡视计划编号为：{result2}")

            df.insert(df.columns.get_loc('序号') + 1, '配网工单编号', pd.NA)
            for pn in plan_numbers:
                df.loc[pn['row'] - 1, '配网工单编号'] = pn['number']
            empty_plan_mask = df['配网工单编号'].isna() | (df['配网工单编号'].astype(str).str.strip() == '')
            df.loc[empty_plan_mask, '工单创建日期'] = pd.NA
            df.to_excel(str(filename), index=False)

            # 回写到全量数据表
            self._backfill_plan_data(df, filename2, plan_numbers, step=step+5, flow=flow)

        else:
            print("未能创建任何巡视计划")

        # 清理临时文件
        # self._cleanup_temp_files()

        print("巡视计划创建流程已结束")
        report(step+5, "巡视计划创建流程已结束", flow=flow)
        # remote_log("FINISH", "巡视计划创建流程已结束", batch_id=step+5)

    def _backfill_plan_data(self, df, filename2, plan_numbers, step, flow):
        """用filename内容回写到filename2，通过台区名称+巡视日期匹配，只回写配网工单编号和工单创建日期"""
        try:
            df2 = pd.read_excel(filename2)
            matched_count = 0

            for pn in plan_numbers:
                row_idx = pn['row'] - 1
                target_name = df.loc[row_idx, '台区名称']
                target_patrol_date = df.loc[row_idx, '巡视日期']
                target_number = df.loc[row_idx, '配网工单编号']
                target_create_date = df.loc[row_idx, '工单创建日期']

                # 匹配台区名称+巡视日期，且配网/营销工单编号都为空
                mask = (
                    (df2['台区名称'] == target_name) &
                    (df2['巡视日期'] == target_patrol_date) &
                    (df2['配网工单编号'].isna() | (df2['配网工单编号'].astype(str).str.strip() == '')) &
                    (df2['营销工单编号'].isna() | (df2['营销工单编号'].astype(str).str.strip() == ''))
                )

                match_indices = df2[mask].index
                if len(match_indices) > 0:
                    idx = match_indices[0]
                    df2.loc[idx, '配网工单编号'] = target_number
                    df2.loc[idx, '工单创建日期'] = target_create_date
                    matched_count += 1
                else:
                    print(f"警告：filename2 中未找到匹配行（台区名称={target_name}, 巡视日期={target_patrol_date}）")

            df2.to_excel(filename2, index=False)
            print(f"已回写到 {filename2.name}，共匹配回写 {matched_count} 行")
            report(step, f"已回写到 {filename2.name}，共匹配回写 {matched_count} 行", flow=flow)
        except Exception as e:
            print(f"警告：回写 {filename2.name} 时出错：{e}")

    def _cleanup_temp_files(self):
        """清理临时文件"""
        try:
            """
            data = self._load_patrol_plan_data()
            if data is not None:
                _, filename, _ = data
                if filename and Path(str(filename)).exists():
                    bak_path = Path(str(filename)).with_suffix(Path(str(filename)).suffix + '.bak')
                    Path(str(filename)).rename(bak_path)
            """

            create_excel_path = Path("./create_excel.py")
            if create_excel_path.exists():
                create_excel_path.unlink()
        except Exception as e:
            print(f"清理临时文件失败: {e}")

    @staticmethod
    def run(**kwargs):
        """执行"""
        obj = Base()
        obj.main(**kwargs)

    def main(self, **kwargs):
        """
        主入口：编排创建巡视计划的所有步骤
        """
        mode = get_mode()
        flow_name = '低压台区巡视计划创建'

        with ExitStack() as stack:
            p1 = stack.enter_context(sync_playwright())
            browser = p1.chromium.launch(
                executable_path=r'C:\.hermes\chromium\chrome.exe',
                headless=(mode == '1'),
                args=[
                    '--disable-features=Translate',
                    '--disable-translate',
                    '--no-first-run',
                    '--no-default-browser-check',
                    "--start-maximized"
                ]
            )

            page = Browser(browser)

            report(1, "浏览器启动完成", flow=flow_name)
            self._login(page, step=2, flow=flow_name)
            # time.sleep(100000)
            self._open_new_work_order(page, step=3, flow=flow_name)
            self._create_patrol_plans(page, step=4, flow=flow_name)


def main(**kwargs):
    report_all({"低压台区巡视计划创建": [
        "启动浏览器",
        "登录系统",
        "进入巡视工单管理页面",
        "选择巡视计划时间",
        "选择巡视设备",
        "选择巡视子类",
        "选择重要程度、巡视要求",
        "创建巡视计划",
        "回写工单编号"
    ]})
    Base.run(**kwargs)
    # report_all([])


if __name__ == '__main__':
    main()
