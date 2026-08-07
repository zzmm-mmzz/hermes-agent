# -*- coding:utf-8 -*-

import sys
import io
# import re
# import time
# import ctypes
# import win32api
# import win32con
# from abc import ABC, abstractmethod

from base64 import b64encode

# import argparse
# from contextlib import ExitStack

# Playwright 同步 API
# from playwright.sync_api import Playwright, sync_playwright, expect
from .utils import *

import numpy as np
# import pandas as pd

# from io import StringIO


class Base():

    def __init__(self):
        pass

    @staticmethod
    def run(**kwargs):
        """执行工单审核"""
        obj = Base()
        print("> 正在审核工单，请稍后")
        obj.main(**kwargs)

    def _wait_loading_done(self, page,page2, timeout=60000,step = None,flow=None):
        """等待页面 loading 消失（检测 div.el-loading-mask 是否隐藏）
        Args:
            page: 顶层 page 对象
            timeout: 最长等待时间毫秒，默认60秒
        """
        page.wait_for_timeout(2000)
        try:
            import time
            deadline = time.time() + timeout / 1000
            while time.time() < deadline:
                try:
                    count = page2.locator('div.el-loading-mask:not([style*="display: none"]):not([style*="none"])').count()
                    if count == 0:
                        # print(count)
                        # time.sleep(2)
                        page.wait_for_timeout(1000)
                        return
                except Exception:
                    pass
                page.wait_for_timeout(500)
            print("等待 loading 超时")
            if step:
                report(step,"等待 loading 超时",flow=flow)
        except Exception as e:
            print(f"等待 loading 失败: {e}")
            if step:
                report(step, f"等待 loading 失败: {e}",flow=flow)

    @staticmethod
    def pre_audit(**kwargs):
        """获取审核清单"""
        obj = Base()
        print("> 正在获取待审核工单，请稍后")
        obj.list_main(**kwargs)

    @step_wrapper
    def _login(self, page, step, flow):
        """登录营销2.0"""
        page.login_yx20()
        report(step, "登录营销2.0完成", flow=flow)

    @step_wrapper
    def _switch_role(self, page, role, step, flow):
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
    def _open_digital_station(self, page, step, flow):
        """打开数字化供电所（全业务工单）系统"""
        page.get_by_role("textbox", name="请输入内容").click()
        page.get_by_role("textbox", name="请输入内容").fill("数字化供电所")
        page.locator("div.el-submenu__title").get_by_text('数字化运营').click()
        with page.expect_popup() as page1_info:
            page.get_by_text("数字化供电所（全业务工单）").click()
        page1 = page1_info.value
        width = win32api.GetSystemMetrics(0)
        height = win32api.GetSystemMetrics(1)
        page1.set_viewport_size({"width": width, "height": height})
        report(step, "打开数字化供电所（全业务工单）系统完成", flow=flow)
        return page1

    @step_wrapper
    def _open_pending_task_page(self, page1, step, flow):
        """打开待办工单页面"""
        page1.get_by_role("textbox", name="请输入内容").click()
        page1.get_by_role("textbox", name="请输入内容").fill("待办工单")
        page1.locator("div.navMenu div.el-submenu__title span.second-sub-title").get_by_text("业务工单管理").click()
        page1.locator("div.navMenu div.el-submenu__title span.second-sub-title").get_by_text("工单管理", exact=True).click()
        page1.get_by_role("menuitem", name="待办工单").click()
        report(step, "打开待办工单页面完成", flow=flow)

    @step_wrapper
    def _filter_work_types(self, page2, step, flow):
        """筛选现场电费催收和月结电费催收"""
        page2.get_by_title("工单类型").locator("i").click()
        page2.get_by_role("textbox", name="请输入关键字过滤").click()
        page2.get_by_role("textbox", name="请输入关键字过滤").fill("电费催")
        page2.locator("span.el-tree-node__label", has_text='现场电费催缴').first.wait_for(timeout=8000)
        page2.locator("span.el-tree-node__label").get_by_text('现场电费催缴', exact=True).click()
        page2.locator("span.el-tree-node__label").get_by_text('月结电费催收', exact=True).click()
        page2.get_by_role("button", name="保存").click()
        report(step, "已筛选现场电费催收和月结电费催收", flow=flow)
        page2.locator('label[for=stepName]+div input').click()
        page2.locator('ul.el-select-dropdown__list li.el-select-dropdown__item span').get_by_text('工单审核', exact=True).click()
        page2.locator('label[for=workItemStat]+div input').click()
        page2.locator('ul.el-select-dropdown__list li.el-select-dropdown__item span').get_by_text('未签收', exact=True).click()

    @step_wrapper
    def _query_pending_worksts(self, page2, step, flow):
        """查询待办工单"""
        page2.locator('label[for=workItemStat]+div input').click()
        page2.locator('ul.el-select-dropdown__list li.el-select-dropdown__item span').get_by_text('已签收', exact=True).click()
        page2.locator('label[for=stepName]+div input').click()
        page2.locator('ul.el-select-dropdown__list li.el-select-dropdown__item span').get_by_text('工单审核', exact=True).click()
        page2.get_by_role("button", name="查询").click()
        report(step, "查询待办工单完成", flow=flow)

    @step_wrapper
    def _read_audit_excel(self, step, flow):
        """读取待审核工单.xlsx"""
        df = pd.read_excel("待审核工单.xlsx", dtype={"业务编号": "str"})
        report(step, "已读取待审核工单.xlsx", flow=flow)
        return df

    @step_wrapper
    def _batch_check_balance(self, page, df, step, flow):
        """批量查询用户余额"""
        conns = list(set(df["业务编号"].to_list()))
        balance_dict = self.check_balance(page, *conns)
        report(step, "批量查询用户余额完成", flow=flow)
        return balance_dict

    @step_wrapper
    def _filter_positive_balance(self, df, balance_dict, step, flow):
        """筛选用户余额大于0的工单"""
        df["欠费状态"] = "Y"
        df["实时可用余额"] = df["业务编号"].map(balance_dict).fillna(0)
        df.loc[df['业务编号'].isin(balance_dict.keys()) & (df['实时可用余额'] >= 0), "欠费状态"] = "N"
        report(step, "已查询用户欠费情况", flow=flow)
        return df

    def _process_single_workst(self, page, page1, page2, workst, user,flag="N"):
        """处理单个工单（工具方法，不参与步骤编排）
            flag: 欠费状态 Y 欠费 N 不欠费
        """
        page2.locator('label[for=wkOrderNo]+div input').fill(workst)
        page2.get_by_role("button", name="查询").click()

        cl = page2.locator("div.card-third-box_yx div.pendingtask-table div.el-table__body-wrapper tbody tr").locator('td a').get_by_text("审核").all()
        if not cl:
            return None
        cl[0].click()

        page3 = page1.locator('iframe[src*="/gds/fswoctrl"]').content_frame

        if flag == 'N':
            page3.locator('div[title="审核结果"] label[role="radio"] span.el-radio__label').get_by_text('通过',exact=True).click()
        else:
            page3.locator('div[title="审核结果"] label[role="radio"] span.el-radio__label').get_by_text('不通过',exact=True).click()

        page3.locator('div.card-first-box_yx > div.sg-btnGrounp button').get_by_text('保存', exact=True).click()

        tag = page1.locator('div.page-tag.active').first
        if tag.locator('div.page-title span').text_content() == '工单审核':
            tag.locator('i').click()
        return workst

    @step_wrapper
    def _execute_audit(self, page, page1, page2, df, step, flow):
        """执行待办工单审核"""
        worksts = []
        for idx in df.index:
            record = df.loc[idx]
            workst = record['工单编号'].rstrip('超')
            user = record['处理人']
            flag = record["欠费状态"]
            result = self._process_single_workst(page, page1, page2, workst, user,flag)
            if result:
                worksts.append(result)
                remote_log("APPROVE", "待办工单审核完成", batch_id=step, workst_no=result, workst_tp='实时电费催缴')
        report(step, "待办工单审核完成", flow=flow)
        return worksts

    def _print_audit_result(self, df, worksts):
        """打印审核结果（工具方法）- 已审核通过和不通过分表显示"""
        df = df[df["工单编号"].isin(worksts)].copy()

        df_pass = df[df["欠费状态"] == "N"].copy()
        df_fail = df[df["欠费状态"] == "Y"].copy()

        columns = [x for x in df.columns]
        if not df_pass.empty:
            self.desc_data(df_pass[columns])
        else:
            print("（无）")

        if not df_fail.empty:
            self.desc_data(df_fail[columns])
        else:
            print("（无）")

    def desc_data(self, df):
        """打印数据（纯markdown表格，包含标题行在前）"""
        columns = list(df.columns)
        records = list(df.values)
        print()
        print("| " + " | ".join(columns) + " |")
        print("| " + " | ".join(map(lambda x: "---", columns)) + " |")
        for record in records:
            print("| " + " | ".join(map(lambda x: str(x), record)) + " |")

    def sign_work_st(self, page2):
        """签收工单"""
        records = page2.locator("div.card-third-box_yx div.pendingtask-table tbody tr").all()
        page2.locator('span.el-pagination__sizes input').click()
        page2.locator('body > div.el-select-dropdown ul.el-select-dropdown__list li.el-select-dropdown__item span').get_by_text('条/页').get_by_text('50').click()
        records = page2.locator('div.card-third-box_yx div.pendingtask-table div.el-table__body-wrapper tbody tr').all()
        if records:
            page2.locator('div.card-third-box_yx div.pendingtask-table div.el-table__fixed div.el-table__fixed-header-wrapper thead tr th div.cell label.el-checkbox').click()
            page2.locator('div.sg-btnGrounp button span').get_by_text('签收', exact=True).click()

    def check_balance(self, page, *conns):
        """批量查询余额"""
        page.get_by_role("textbox", name="请输入内容").click()
        page.get_by_role("textbox", name="请输入内容").fill("客户360视图")
        page.locator(".el-submenu__title").click()
        page.locator("div").filter(has_text=re.compile(r"^客户信息$")).nth(1).click()
        page.get_by_text("客户360视图").click()
        page.get_by_text("客户360视图").nth(1).click()
        page3 = page.locator("iframe[src*='/custmgt/cust360viewplus/diansouViews']").content_frame
        page3.get_by_role("textbox", name="输入客户编号（用电户编号、发电户编号）/客户名称（用电户名称、发电户名称）/客户地址（用电地址、发电地址）/合同账户编号").click()
        page3.get_by_role("button", name="查询").click()
        page3.locator("label:text('检索方式')+div.el-form-item__content input").click()
        page3.locator("body>div.el-select-dropdown ul li span").get_by_text('客户或用户编号').click()

        result = {}
        for cons_no in conns:
            try:
                page3.get_by_role("textbox", name="输入客户编号").fill(cons_no)
                page3.get_by_role("button", name="查询").click()
                page3.get_by_role("link", name=cons_no).click(timeout=5000)
                page4 = page.locator("iframe[src*='/custmgt/cust360viewplus/elecCustViewTab']").content_frame
                page4.get_by_text("用户电费/交费信息").click()
                # 等待实时可用余额加载完成（结合显式等待 + 重试机制）
                balance_text = None
                for attempt in range(3):
                    try:
                        balance_label = page4.locator("label:text('实时可用余额') + div.item-val > span:not([class=unitstyle])").first
                        balance_label.wait_for(timeout=15000, state="visible")
                        page.page.wait_for_timeout(2000)
                        balance_text = balance_label.text_content(timeout=5000)
                        if balance_text and balance_text.strip():
                            break
                    except Exception:
                        page.page.wait_for_timeout(3000)
                if balance_text is None or not balance_text.strip():
                    raise Exception("余额加载失败：重试3次后仍无法获取")
                balance = float(balance_text)
                result[cons_no] = float(balance)
                print(f"  {cons_no} → 实时可用余额: {balance}")
            except Exception as e:
                print(f"  {cons_no} → 余额查询失败: {e}")
                pass

            tag = page.locator('div.page-tag.active').first
            if tag.locator('div.page-title span').text_content() == '用电客户视图':
                tag.locator('i').click()

        return result

    def download(self, page2, page):
        """导出数据"""

        def get_data(p):
            page2.locator('span.el-pagination__jump div input').fill(f'{p}')
            page2.get_by_role("button", name="查询").click()
            page2.locator('div.el-table__body-wrapper').wait_for()
            page.page.wait_for_timeout(1000)  # 表格刷新留缓冲
            temp = page2.locator('div.el-table__body-wrapper').evaluate("el => el.innerHTML")
            # print(temp)
            stream = StringIO(temp)
            return pd.read_html(stream,match="", flavor='lxml')[0]

        size = page2.locator('span.el-pagination__total').text_content()
        size = int(re.findall('(\d+)', size)[0])

        headers = [x.text_content().strip() for x in page2.locator('div.el-table__header-wrapper th').all()]
        if headers[-1].strip() == "":
            headers = headers[:-1]

        columns = ["序号", "工单编号", "专业分类", "业务类型", "工作场景", "环节名称", "工作内容/作业内容", "工单类型", "工单时限", "工单计划完成时间", "处理人", "业务编号"]

        if size > 0:
            page2.locator('div.card-third-box_yx div.pendingtask-table div.el-table__body-wrapper')
            df = get_data(1)
            df.columns = headers
        else:
            df = pd.DataFrame()
            for col in headers:
                df[col] = []

        df = df[columns].copy()

        # df = df[df["处理人"] == USERNAME].copy()
        # df = df.loc[:1,:]
        # df["工作内容/作业内容"] = '该用户实时欠费大于预警金额，需催费。'
        return df

    def main(self, **kwargs):
        mode = get_mode()
        flow_name = "工单审核"
        if mode == '0':
            active()
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
            report(1, "浏览器启动完成", flow=flow_name)

            self._login(page, step=2, flow=flow_name) # 登录
            self._switch_role(page, role="站所-全业务工单", step=3, flow=flow_name) # 切换角色
            page1 = self._open_digital_station(page, step=4, flow=flow_name) # 打开供电所
            self._open_pending_task_page(page1, step=5, flow=flow_name)  # 打开待办工单
            page2 = page1.locator("iframe[src*='/gds/fswostdmgt/pendingtask']").content_frame
            self._filter_work_types(page2, step=6, flow=flow_name) # 筛选现场电费催收和月结电费催收
            self._query_pending_worksts(page2, step=7, flow=flow_name) # 查询待办工单
            df = self._read_audit_excel(step=8, flow=flow_name) # 读取待审核工单（已含实时可用余额和欠费状态）
            # 审核前汇总
            total = len(df)
            settled = len(df[df["欠费状态"] == "N"])
            unsettled = len(df[df["欠费状态"] == "Y"])
            print(f"\n待审核催费工单总计{total}条，其中已结清欠费工单{settled}条，未结清欠费工单{unsettled}条\n")
            worksts = self._execute_audit(page, page1, page2, df, step=9, flow=flow_name) # 执行待办工单审核
            self._print_audit_result(df, worksts) # 打印审核结果
            # 审核后汇总
            df_pass = df[df["欠费状态"] == "N"]
            df_fail = df[df["欠费状态"] == "Y"]
            done = len(worksts)
            pass_cnt = len(df_pass)
            fail_cnt = len(df_fail)
            print(f"\n已完成{done}条工单审核，其中结清欠费工单{pass_cnt}条已审核闭环，未结清欠费工单{fail_cnt}条已驳回")
            report(10, "工单审核完成", flow=flow_name) # 完成

    def list_worksts(self, **kwargs):
        """获取待审核工单（兼容旧调用）"""
        return self.list_main(**kwargs)

    def list_main(self, **kwargs):
        """主入口：编排所有步骤 - 获取待审核工单"""
        mode = get_mode()
        flow_name = "获取待审核工单"
        if mode == '0':
            active()
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
            report(1, "浏览器启动完成", flow=flow_name)

            self._login(page, step=2, flow=flow_name)
            self._switch_role(page, role="站所-全业务工单", step=3, flow=flow_name)
            page1 = self._open_digital_station(page, step=4, flow=flow_name)
            self._open_pending_task_page(page1, step=5, flow=flow_name)
            page2 = page1.locator("iframe[src*='/gds/fswostdmgt/pendingtask']").content_frame
            self._filter_work_types(page2, step=6, flow=flow_name)
            self._query_pending_tasks(page2, step=7, flow=flow_name)
            self._sign_worksts(page2, step=8, flow=flow_name)
            self._filter_signed_worksts(page2, page, step=9, flow=flow_name)
            self._export_audit_list(page2, page, step=10, flow=flow_name)
            df = self._read_audit_excel(step=11, flow=flow_name)
            conns = self._batch_check_balance(page, df, step=12, flow=flow_name)
            df = self._filter_positive_balance(df, conns, step=13, flow=flow_name)
            # 将余额查询结果写回 Excel（覆盖导出的默认值）
            df.to_excel("待审核工单.xlsx", index=False)
            self._print_audit_list_with_balance(df, page2, step=14, flow=flow_name)
            
    @step_wrapper
    def _query_pending_tasks(self, page2, step, flow):
        """查询待办工单（预审核）"""
        page2.get_by_role("button", name="查询").click()
        report(step, "查询待办工单完成", flow=flow)

    @step_wrapper
    def _sign_worksts(self, page2, step, flow):
        """签收待办工单"""
        self.sign_work_st(page2)
        report(step, "签收待办工单完成", flow=flow)

    @step_wrapper
    def _filter_signed_worksts(self, page2, page, step, flow):
        """筛选已签收工单"""
        page2.locator('label[for=workItemStat]+div input').click()
        page2.locator('ul.el-select-dropdown__list li.el-select-dropdown__item span').get_by_text('已签收', exact=True).click()
        page2.locator('label[for=stepName]+div input').click()
        page2.locator('ul.el-select-dropdown__list li.el-select-dropdown__item span').get_by_text('工单审核', exact=True).click()
        page2.get_by_role("button", name="查询").click()
        self._wait_loading_done(page.page, page2, timeout=60000,step = step,flow=flow) # 等待加载中结束
        report(step, "筛选已签收工单完成", flow=flow)

    @step_wrapper
    def _export_audit_list(self, page2, page, step, flow):
        """待审核工单导出"""
        df = self.download(page2, page)
        # 导出时初始化欠费状态和实时可用余额列（后续 pre_audit 流程会填充）
        df["欠费状态"] = "Y"
        df["实时可用余额"] = 0
        df.to_excel("待审核工单.xlsx", index=False)
        report(step, "待审核工单导出完成", flow=flow)

    @step_wrapper
    def _print_audit_list_with_balance(self, df, page2, step, flow):
        """打印带实时余额的待审核工单列表"""
        if df.empty:
            print("\n> 待审核工单（含余额查询）：（无）")
            report(step, "待审核工单任务完成（无工单）", flow=flow)
            return
        print("\n> 待审核工单（含实时余额）：")
        self.desc_data(df)
        total = len(df)
        settled = len(df[df["欠费状态"] == "N"])
        unsettled = len(df[df["欠费状态"] == "Y"])
        print(f"\n待审核催费工单总计{total}条，已结清{settled}条，未结清{unsettled}条")
        report(step, "待审核工单任务完成", flow=flow)


def main(**kwargs):
    report_all({"工单审核":['打开浏览器', '登录系统', '岗位切换', '打开全量业务工单', '打开待办工单页面', '筛选现场电费催收和月结电费催收', '查询待办工单', '读取待审核工单', '执行待办工单审核', '工单审核完成']})
    Base.run(**kwargs)
    # report_all([])

def pre_audit(**kwargs):
    report_all({"获取待审核工单":['打开浏览器', '登录系统', '岗位切换', '打开全量业务工单', '打开待办工单页面', '筛选现场电费催收和月结电费催收', '查询待办工单', '签收待办工单', '筛选已签收工单', '待审核工单导出', '读取待审核工单', '批量查询用户余额', '筛选用户余额大于0的工单', '打印待审核工单']})
    Base.pre_audit(**kwargs)
    # report_all([])


if __name__ == '__main__':
    main()
