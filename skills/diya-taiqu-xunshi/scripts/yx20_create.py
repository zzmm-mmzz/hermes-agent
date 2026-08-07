# -*- coding:utf-8 -*-
# import re
from pathlib import Path
# import time
# import pandas as pd
# from io import StringIO
# from contextlib import ExitStack

# from playwright.sync_api import sync_playwright

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from .utils import *


class Base():
    """待审批工单清单查询"""

    def __init__(self):
        super().__init__()
        self.mode = get_mode()

    @step_wrapper
    def _login(self, page, step, flow):
        """登录营销2.0"""
        page.login_yx20()
        report(step, "已登录至营销2.0", flow=flow)
        # remote_log("SELECT","登录营销2.0完成",batch_id=step)
    """
    def _switch_role_pre(self, page, step, flow):
        # 切换岗位-全业务工单
        mapping = {
            "站所-全业务工单": [
                "站所-员工-工单调度员（综合柜员）",
                "站所-班组长-网格服务班（组）长",
                "站所-班组长-市场营销班班长",
                "站所-班组长-站所长",
                "站所-员工-网格服务班网格服务经理",
                "站所-员工-能效服务经理",
                "站所-员工-营销服务经理",
                "站所-员工-网格服务班工单调度员",
                "站所-全业务工单"
            ]
        }
        try:
            job_list = page.locator('div[title="切换岗位"] div[title] span').all()
            available_roles = [role.text_content().strip() for role in job_list] if job_list else []

            target_role = None
            for role_group, candidates in mapping.items():
                if role_group in available_roles:
                    target_role = role_group
                    break
                for candidate in candidates:
                    if candidate in available_roles:
                        target_role = candidate
                        break
                if target_role:
                    break

            if not target_role:
                raise ValueError(f"未匹配到相应岗位，期望映射: {mapping}，可用岗位: {available_roles}")

            page.switch_role(target_role)
            report(step, f"切换岗位【{target_role}】成功", flow=flow)
            remote_log("EDIT",f"切换岗位-{target_role}成功",batch_id=step)

        except Exception as e:
            raise RuntimeError(f"切换岗位失败: {e}") from e
    """

    @step_wrapper
    def _switch_role(self, page, role, step, flow=None):
        """切换岗位，如果切换不了则强制报错"""
        page.wait_for_timeout(3000)

        # 直接用 evaluate 获取岗位列表
        available_roles = page.page.evaluate("""() => {
            const spans = document.querySelectorAll('div[title="切换岗位"] div[title] span');
            return Array.from(spans).map(s => s.textContent.trim());
        }""")

        mapping = {
            "站所-班组长-站所长":[
                "站所-员工-能效服务经理",
                "站所-员工-营销服务经理",
                "站所-班组长-站所长",
                "站所-班组长-市场营销班班长",
                "站所-员工-营销技术员"
            ],
            "站所-全业务工单":[
                "站所-员工-工单调度员（综合柜员）",
                "站所-班组长-网格服务班（组）长",
                "站所-班组长-市场营销班班长",
                "站所-班组长-站所长",
                "站所-员工-网格服务班网格服务经理",
                "站所-员工-能效服务经理",
                "站所-员工-营销服务经理",
                "站所-员工-网格服务班工单调度员",
                "站所-全业务工单"
            ]
        }

        target_role = None
        for role_group, candidates in mapping.items():
            if role_group != role:
                continue
            if role_group in available_roles:
                target_role = role_group
                break
            for candidate in candidates:
                if candidate in available_roles:
                    target_role = candidate
                    break
            if target_role:
                break

        if not target_role:
            raise ValueError(f"未匹配到相应岗位，期望映射: {mapping}，可用岗位: {available_roles}")

        page.page.evaluate(f"""()=>document.querySelector('div[title="{target_role}"]').click()""")

        # 等待岗位切换完成
        current_role = "获取当前岗位失败"
        for i in range(3):
            page.wait_for_timeout(500)
            current_roles = page.page.evaluate("""() => {
                const spans = document.querySelectorAll('div[title="切换岗位"] div.active[title] span');
                return Array.from(spans).map(s => s.textContent.trim());
            }""")
            if current_roles:
                current_role = current_roles[0]
                if current_role == target_role:
                    report(step, f"切换岗位-{target_role}成功", flow=flow)
                    # remote_log("EDIT",f"切换岗位-{target_role}成功",batch_id=step)
                    return

        raise ValueError(f"岗位切换点击失败: {target_role}, 当前岗位为{current_role}")

    @step_wrapper
    def _open_digital_work_order(self, page, step, flow):
        """打开数字化供电所（全业务工单）"""
        page.get_by_role("textbox", name="请输入内容").click()
        page.get_by_role("textbox", name="请输入内容").fill("数字化供电所")
        # time.sleep(0.5)
        page.locator("div.el-submenu__title").get_by_text('数字化运营').click()
        # time.sleep(0.5)
        with page.expect_popup() as page1_info:
            page.get_by_text("数字化供电所（全业务工单）").click()
        page1 = page1_info.value
        if self.mode == '0':
            width = win32api.GetSystemMetrics(0)
            height = win32api.GetSystemMetrics(1)
            page1.set_viewport_size({"width": width, "height": height})
        # time.sleep(1)
        report(step, "打开全量业务工单完成", flow=flow)
        # remote_log("SELECT","打开全量业务工单完成",batch_id=step)
        return page1

    @step_wrapper
    def _open_plan_task_page(self, page, step, flow):
        """打开计划任务池"""
        # page.get_by_role("textbox", name="请输入内容").click()
        # time.sleep(1)
        page.get_by_role("textbox", name="请输入内容").fill("计划任务池")
        # time.sleep(1)
        page.locator("div.navMenu div.el-submenu__title span.second-sub-title").get_by_text("业务工单管理").click()
        # time.sleep(1)
        page.locator("div.navMenu div.el-submenu__title span.second-sub-title").get_by_text("工单创建", exact=True).click()
        # time.sleep(2)
        page.get_by_text("计划任务池").click()
        # time.sleep(1)
        report(step, "已打开计划任务池", flow=flow)
        # remote_log("SELECT","已打开计划任务池",batch_id=step)

    @step_wrapper
    def _filter_by_work_type(self,page1, page2, step, flow):
        """按工单类型筛选-配网设备运维检修-低压台区巡视"""
        page2.locator("div#pane-first").get_by_title("工单类型").locator("i").click()
        # time.sleep(1)
        page2.get_by_title("所属系统").locator("i").click()
        # time.sleep(1)
        page2.locator("li.el-select-dropdown__item").get_by_text('数字化供电所').wait_for(state='visible', timeout=5000)
        page2.locator("li.el-select-dropdown__item").get_by_text('数字化供电所').click()
        # time.sleep(1)
        page2.get_by_title("专业分类").locator("i").click()
        # time.sleep(1)
        page2.locator("li.el-select-dropdown__item").get_by_text('配网设备运维检修').wait_for(state='visible', timeout=5000)
        page2.locator("li.el-select-dropdown__item").get_by_text('配网设备运维检修').click()
        # time.sleep(1)
        """
        page2.get_by_title("业务类型").locator("i").click()
        time.sleep(1)
        page2.locator("li.el-select-dropdown__item").get_by_text('低压台区巡视',exact=True).wait_for(state='visible', timeout=5000000)
        page2.locator("li.el-select-dropdown__item").get_by_text('低压台区巡视',exact=True).click()
        page2.locator("div.dialog-third-box_yx").get_by_text('查询').click()
        """
        page2.locator("div.dialog-inner div.el-input--mini i.el-icon-arrow-up").click()
        page2.get_by_text("50条/页").last.click()
        time.sleep(1)
        target = page2.locator("div.el-table__body-wrapper tr.el-table__row.tableRowClass").get_by_text('低压台区巡视',exact=True)
        if target.count() > 0:
            target.click()
            page2.locator("button.el-button--small").get_by_text('保存').click()
            report(step, "已筛选【低压台区巡视】工单类型", flow=flow)
            # remote_log("SELECT","已筛选【低压台区巡视】工单类型",batch_id=step)
            return

        # 当前页未找到，获取总页数
        number_els = page2.locator("div.el-col-24 li.number").all()
        total_pages = max(int(el.text_content().strip()) for el in number_els)

        if total_pages <= 1:
            raise ValueError("未找到【低压台区巡视】工单类型")

        # 从第2页开始逐页翻页查找
        pagination_input = page2.locator("div.el-col-24 span.el-pagination__jump input.el-input__inner")
        for page_num in range(2, total_pages + 1):
            pagination_input.fill(str(page_num))
            pagination_input.press("Enter")
            time.sleep(1)

            if target.count() > 0:
                target.click()
                page2.locator("button.el-button--small").get_by_text('保存').click()
                report(step, "已筛选【低压台区巡视】工单类型", flow=flow)
                # remote_log("SELECT","已筛选【低压台区巡视】工单类型",batch_id=step)
                return

        raise ValueError(f"已翻遍{total_pages}页，未找到【低压台区巡视】工单类型")

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

    def _create_single_plan(self, page2,page1, plan_code, row_idx, total, step, flow):
        """创建单个低压台区巡视工单"""
        try:
            # 跳转到任务池
            # print(f"开始处理第 {row_idx + 1}/{total} 条：配网编号 {plan_code}")
            # report(step, f"查找配网编号 {plan_code} 在计划池中的记录", flow=flow)

            if page2.locator("td.el-table_1_column_7 div").get_by_text(plan_code).count() > 0:
                page2.locator("td.el-table_1_column_7 div").get_by_text(plan_code).locator("../..").locator("td.el-table_1_column_21 a").first.click()
                remote_log("SELECT", "查询配网工单", batch_id=step, workst_no=plan_code, workst_tp='低压台区巡视-全量业务工单')
            
            # if page2.locator("div#pane-first div.el-table__empty-block").count() == 0:
                # page2.locator("td.el-table_1_column_21 a").first.click()
            else:
                print(f"错误：未找到配网编号 {plan_code} 对应的记录，可能尚未同步")
                report(step, f"错误：未找到配网编号 {plan_code} 对应的记录，可能尚未同步", flow=flow)
                return None
            # time.sleep(10000)
            
            page2.locator("div#pane-second div.el-table__fixed div.el-table__fixed-header-wrapper thead tr th div.cell label.el-checkbox").click()

            page2.get_by_text("批量创建").click()
            page2.get_by_text("确定").click()
            time.sleep(1)
            """
            page2.locator("div#pane-second").get_by_text("查询").click()
            # time.sleep(10000)

            # 获取营销工单编号
            # plan_no = page2.locator("td.el-table_2_column_48 div").first.text_content().strip()
            page2.locator("div.el-table__fixed td.el-table_2_column_48.is-hidden div").first.wait_for(state="attached",timeout=10000)
            plan_no_cells = page2.locator("div.el-table__fixed td.el-table_2_column_48.is-hidden div").all()
            plan_no = ",".join([cell.text_content().strip() for cell in plan_no_cells if cell.text_content().strip()])
            """
            # page1.locator("iframe[src*='/gds/fswosmartrule/planTask']").screenshot(path="screenshot_patrol_type1.png")
            # 点击查询刷新列表
            # print(f"  点击「查询」按钮刷新工单列表（第 {row_idx + 1}/{total} 条，配网编号 {plan_code}）")
            report(step, f"查询刷新工单列表", flow=flow)
            query_btn = page2.locator("div#pane-second").get_by_text("查询")
            if query_btn.count() == 0:
                print(f"  错误：未找到「查询」按钮（配网编号 {plan_code}）")
                report(step, f"错误：未找到「查询」按钮", flow=flow)
                return None
            query_btn.click()
            # page1.locator("iframe[src*='/gds/fswosmartrule/planTask']").screenshot(path="screenshot_patrol_type2.png")
            # 获取营销工单编号
            # print(f"  等待营销工单编号列加载...（第 {row_idx + 1}/{total} 条，配网编号 {plan_code}）")
            report(step, f"获取营销工单编号", flow=flow)
            time.sleep(1)
            try:
                page2.locator("div.el-table__fixed td.el-table_2_column_48.is-hidden div").first.wait_for(state="attached",timeout=10000)
            except Exception as timeout_e:
                print(f"  错误：等待营销工单编号超时（10秒），页面可能未刷新完成（配网编号 {plan_code}）: {timeout_e}")
                report(step, f"错误：获取营销工单编号超时", flow=flow)
                return None
            # page1.locator("iframe[src*='/gds/fswosmartrule/planTask']").screenshot(path="screenshot_patrol_type3.png")
            plan_no_cells = page2.locator("div.el-table__fixed td.el-table_2_column_48.is-hidden div").all()
            cell_texts = [cell.text_content().strip() for cell in plan_no_cells if cell.text_content().strip()]
            # print(f"  获取到 {len(cell_texts)} 个营销工单编号单元格")
            if not cell_texts:
                print(f"  错误：营销工单编号列为空，创建可能未成功（配网编号 {plan_code}）")
                report(step, f"错误：营销工单编号为空，创建可能未成功", flow=flow)
                return None

            plan_no = ",".join(cell_texts)
            # print(f"  营销工单编号: {plan_no}")
            # time.sleep(10000)

            print(f"完成巡视计划创建，配网编号 {plan_code}，营销编号 {plan_no}")
            report(step, f"完成巡视计划创建，编号 {plan_no}）", flow=flow)
            for workst_no in cell_texts:
                remote_log("BATCH_CREATE", "巡视工单创建完成", batch_id=step, workst_no=workst_no, workst_tp='低压台区巡视-全量业务工单')

            return plan_no
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"  异常类型: {type(e).__name__}")
            print(f"  异常信息: {e}")
            print(f"  堆栈跟踪:\n{tb}")
            print(f"创建巡视计划失败（配网编号 {plan_code}）: {e}")
            report(step, f"创建巡视计划失败: {e}", flow=flow)
            return None

    @step_wrapper
    def _create_patrol_plans(self, page2, page1, step, flow):
        """创建低压台区巡视工单（只取第一条配网工单编号，回写所有匹配行）"""
        data = self._load_patrol_plan_data()
        if data is None:
            return
        df, filename, filename2 = data

        # 检查是否有 配网工单编号 列
        if '配网工单编号' not in df.columns:
            print("错误：清单文件缺少「配网工单编号」列，请先在配网微应用创建巡视计划")
            report(step, "错误：清单文件缺少「配网工单编号」列", flow=flow)
            return

        # 取第一个有效的配网工单编号
        first_plan_code = None
        first_row_idx = None
        for row_idx, row in df.iterrows():
            plan_code = row.get('配网工单编号', None)
            if pd.notna(plan_code) and str(plan_code).strip() != '':
                first_plan_code = str(plan_code).strip()
                first_row_idx = row_idx
                break

        if first_plan_code is None:
            print("错误：未找到有效的配网工单编号")
            report(step, "错误：未找到有效的配网工单编号", flow=flow)
            return

        print(f"--- 正在查找配网工单编号 {first_plan_code} 对应的计划 ---")
        report(step, f"正在查找配网工单编号 {first_plan_code} 对应的计划", flow=flow)

        # 创建单个工单
        plan_no = self._create_single_plan(page2, page1, first_plan_code, first_row_idx, len(df), step=step, flow=flow)

        if plan_no:
            # 回写到 filename：所有配网工单编号匹配的行
            df.insert(df.columns.get_loc('配网工单编号') + 1, '营销工单编号', pd.NA)
            match_mask = df['配网工单编号'].astype(str).str.strip() == first_plan_code
            df.loc[match_mask, '营销工单编号'] = plan_no
            df.loc[~match_mask, '工单创建日期'] = pd.NA
            df.to_excel(str(filename), index=False)

            # 回写到全量数据表
            self._backfill_plan_data(filename2, first_plan_code, plan_no, step=step, flow=flow)

            # 返回计划池，准备处理下一条
            # page2.get_by_text('计划池').click()
            # time.sleep(1)

        else:
            print("未能创建巡视计划")

        # 清理临时文件
        self._cleanup_temp_files()

        print("巡视计划创建流程已结束")
        report(step, "巡视计划创建流程已结束", flow=flow)
        # remote_log("FINISH", "巡视计划创建流程已结束", batch_id=step)

    def _backfill_plan_data(self, filename2, plan_code, plan_no, step, flow):
        """回写营销工单编号到全量数据表（所有匹配配网工单编号的行）"""
        try:
            df2 = pd.read_excel(filename2)

            match_mask = df2['配网工单编号'].astype(str).str.strip() == plan_code
            if match_mask.any():
                df2.loc[match_mask, '营销工单编号'] = plan_no
                df2.to_excel(filename2, index=False)
                matched_count = int(match_mask.sum())
                print(f"已回写到 {filename2.name}，共 {matched_count} 行")
            else:
                print(f"警告：全量数据表中未找到配网工单编号 {plan_code}，跳过回写")

        except Exception as e:
            print(f"警告：回写 {filename2.name} 时出错：{e}")

    def _cleanup_temp_files(self):
        """清理临时文件"""
        try:
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
            """
        except Exception as e:
            print(f"清理临时文件失败: {e}")

    @staticmethod
    def run(**kwargs):
        """执行"""
        obj = Base()
        obj.main(**kwargs)

    def main(self, **kwargs):
        """
        主入口：编排所有步骤
        """
        mode = self.mode
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

            page = YX20(browser)
            report(1, "浏览器已启动", flow=flow_name)

            self._login(page, step=2, flow=flow_name)

            # self._switch_role_pre(page, step=3, flow=flow_name)
            self._switch_role(page, role="站所-全业务工单", step=3, flow=flow_name)

            page1 = self._open_digital_work_order(page, step=4, flow=flow_name)

            # 打开计划任务池页面
            self._open_plan_task_page(page1, step=5, flow=flow_name)

            page4 = page1.locator("iframe[src*='/gds/fswosmartrule/planTask']").content_frame

            # 筛选工单类型
            self._filter_by_work_type(page1,page4, step=6, flow=flow_name)

            # 创建低压台区巡视工单
            self._create_patrol_plans(page4,page1, step=7, flow=flow_name)


def main(**kwargs):
    report_all({"低压台区巡视计划创建": [
        "启动浏览器",
        "登录系统",
        "切换岗位",
        "打开全量业务工单",
        "打开计划任务池页面",
        "筛选工单类型",
        "创建巡视工单"
    ]})
    Base.run(**kwargs)
    # report_all([])


if __name__ == '__main__':
    main()
