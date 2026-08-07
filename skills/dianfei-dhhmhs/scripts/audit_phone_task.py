# -*- coding:utf-8 -*-
# import re
# import time
# import pandas as pd
# from contextlib import ExitStack

# from playwright.sync_api import sync_playwright

from .utils import *


class Base():
    """工单审批"""

    def __init__(self):
        super().__init__()

    @step_wrapper
    def _login(self, page, step, flow):
        """登录营销2.0"""
        page.login_yx20()
        report(step, "登录营销2.0完成", flow=flow)
        # remote_log("SELECT","登录营销2.0完成",batch_id=step)

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
        width = win32api.GetSystemMetrics(0)
        height = win32api.GetSystemMetrics(1)
        if width <= 1920 or height <= 1080:
            width, height = 1920, 1080
        page1.set_viewport_size({"width": width, "height": height})
        # time.sleep(1)
        report(step, "打开全量业务工单完成", flow=flow)
        # remote_log("SELECT","打开全量业务工单完成",batch_id=step)
        return page1

    @step_wrapper
    def _open_pending_task_page(self, page1, step, flow):
        """打开待办工单页面"""
        page1.get_by_role("textbox", name="请输入内容").click()
        # time.sleep(1)
        page1.get_by_role("textbox", name="请输入内容").fill("待办工单")
        # time.sleep(1)
        page1.locator("div.navMenu div.el-submenu__title span.second-sub-title").get_by_text("业务工单管理").click()
        # time.sleep(1)
        page1.locator("div.navMenu div.el-submenu__title span.second-sub-title").get_by_text("工单管理", exact=True).click()
        # time.sleep(1)
        page1.get_by_role("menuitem", name="待办工单").click()
        # time.sleep(1)
        report(step, "打开待办工单页面完成", flow=flow)
        # remote_log("SELECT","打开待办工单页面完成",batch_id=step)

    @step_wrapper
    def _filter_work_type(self, page2, step, flow):
        """筛选电话号码核实工单类型"""
        page2.get_by_title("工单类型").locator("i").click()
        # time.sleep(1)
        page2.get_by_role("textbox", name="请输入关键字过滤").click()
        # time.sleep(1)
        page2.get_by_role("textbox", name="请输入关键字过滤").fill("电费管理-电话号码核实")
        # time.sleep(5)
        page2.locator("span.el-tree-node__label").get_by_text('电费管理-电话号码核实', exact=True).click()
        # time.sleep(1)
        page2.get_by_role("button", name="保存").click()
        report(step, "已筛选【电费管理-电话号码核实】工单类型", flow=flow)
        # remote_log("SELECT","已筛选【电费管理-电话号码核实】工单类型",batch_id=step)

    @step_wrapper
    def _query_signed_orders(self, page2, page1, step, flow):
        """查询已签收+工单处理的待办工单"""
        page2.locator('label[for=workItemStat]+div input').wait_for(state='visible', timeout=5000)
        page2.locator('label[for=workItemStat]+div input').click()
        # time.sleep(1)
        page2.locator('ul.el-select-dropdown__list li.el-select-dropdown__item span').get_by_text('已签收', exact=True).click()
        # time.sleep(1)

        page2.locator('label[for=stepName]+div input').click()
        # time.sleep(1)
        page2.locator('ul.el-select-dropdown__list li.el-select-dropdown__item span').get_by_text('工单处理', exact=True).click()
        # time.sleep(1)

        page2.locator('span.el-pagination__sizes input').click()
        page2.locator('body > div.el-select-dropdown ul.el-select-dropdown__list li.el-select-dropdown__item span').get_by_text('条/页').get_by_text('50').click()
        # page1.wait_for_load_state('networkidle')
        report(step, "查询待办工单完成", flow=flow)
        # remote_log("SELECT","查询待办工单完成",batch_id=step)

    @step_wrapper
    def _load_audit_data(self, step, flow):
        """读取待审核工单.xlsx"""
        df = pd.read_excel("待审核工单.xlsx", dtype={"业务编号": "str"})
        report(step, "读取待审核工单.xlsx", flow=flow)
        # remote_log("SELECT","读取待审核工单数据完成",batch_id=step)
        return df

    def _select_user(self, page, user):
        """选择人员"""
        try:
            page.locator('div.el-dialog__body span.el-pagination__sizes input').first.click()
            # time.sleep(1)
            page.locator('body > div.el-select-dropdown ul.el-select-dropdown__list li.el-select-dropdown__item span').get_by_text('50条/页').click()
            # time.sleep(1)
            records = page.locator("div.dialog-inner div.dialog-body div.el-table__fixed-body-wrapper tbody tr").all()
            rows = []
            for record in records:
                vals = [x.text_content() for x in record.locator('td').all()]
                rows.append(vals[5])

            if rows.count(user):
                records[rows.index(user)].click()
                # time.sleep(1)
                page.locator('div.sg-btnGrounp-dialog button span').get_by_text('保存').click()
                return user
            else:
                print(f"{user}不存在")
                return None
        except Exception as e:
            print(f"选择人员失败: {e}")
            return None

    def _add_cyd(self, page, user, value):
        """添加参与度"""
        try:
            records = page.locator("div[tabctitle=人员参与度] div.el-table__body-wrapper table tbody tr").all()
            rows = []
            for record in records:
                vals = [x.text_content() for x in record.locator('td').all()]
                rows.append(vals[3])

            if rows.count(user):
                ss = records[rows.index(user)].locator('td').all()[5]
                records[rows.index(user)].locator('td').all()[5].click()
                ss.highlight()
                # time.sleep(2)
                records[rows.index(user)].locator('td').all()[5].locator('input').fill(f'{value}')
                records[rows.index(user)].locator('td').all()[4].click()
                # time.sleep(1)
                page.locator('body>div.el-select-dropdown ul.el-scrollbar__view li.el-select-dropdown__item span').get_by_text('负责人').click()
                # time.sleep(1)
            else:
                print(f"{user}不存在")
        except Exception as e:
            print(f"添加参与度失败: {e}")

    def _set_zone(self, page3, value="农村"):
        """选择区域"""
        try:
            page3.locator('label:text("区域")+div input').click()
            # time.sleep(1)
            page3.locator('ul.el-select-dropdown__list li.el-select-dropdown__item').get_by_text(value).click()
        except Exception as e:
            print(f"选择区域失败: {e}")

    def _set_terrain(self, page3, value='丘陵'):
        """选择地形"""
        try:
            page3.locator('label:text("地形")+div input').click()
            # time.sleep(1)
            page3.locator('ul.el-select-dropdown__list li.el-select-dropdown__item').get_by_text(value).click()
        except Exception as e:
            print(f"选择地形失败: {e}")

    def _set_weather(self, page3, value="雨天"):
        """选择天气类型"""
        try:
            page3.locator('label:text("天气类型")+div input').click()
            # time.sleep(1)
            page3.locator('ul.el-select-dropdown__list li.el-select-dropdown__item').get_by_text(value).click()
        except Exception as e:
            print(f"选择天气类型失败: {e}")

    def _audit_single_order(self, page1, step, workst, user):
        """审核单个工单"""
        try:
            tag = page1.locator('div.page-tag.active').first
            if tag.locator('div.page-title span').text_content() in ('审核流程处理', '工单处理'):
                tag.locator('i').click()
                # time.sleep(1)

            page2 = page1.locator("iframe[src*='/gds/fswostdmgt/pendingtask']").content_frame
            page2.locator('label[for=wkOrderNo]+div input').fill(workst)
            # time.sleep(1)
            page2.get_by_role("button", name="查询").click()
            # time.sleep(2)
            remote_log("SELECT", "查询待办工单", batch_id=step, workst_no=workst, workst_tp='电话号码核实')
            # 点击处理
            cl = page2.locator("div.card-third-box_yx div.pendingtask-table div.el-table__body-wrapper tbody tr").locator('td a').get_by_text("处理").all()
            if not cl:
                return False
            cl[0].click()
            # time.sleep(1)

            page3 = page1.locator('iframe[src*="/gds/fswoctrl"]').content_frame

            try:
                # time.sleep(1)
                tips = page3.get_by_role("button", name="我已知晓").all()
                if tips:
                    tips[0].click()
            except Exception:
                pass

            page3.locator('div.jxm-tab-label').get_by_text('人员参与度').click()

            # 区域/地形/天气
            self._set_zone(page3, '农村')
            self._set_terrain(page3, '丘陵')
            self._set_weather(page3, '雨天')

            # 清除所有人员
            lines = page3.locator('div[tabctitle="人员参与度"] div.el-table__fixed-right div.el-table__fixed-body-wrapper tr button span').all()
            for _ in lines:
                # time.sleep(1)
                page3.locator('div[tabctitle="人员参与度"] div.el-table__fixed-right div.el-table__fixed-body-wrapper tr button span').first.click()

            # 选择人员
            page3.locator('div[tabctitle="人员参与度"] div.sg-title-btn-box span').get_by_text("选择人员").click()
            # time.sleep(1)
            empl = self._select_user(page3, user)
            # time.sleep(1)
            self._add_cyd(page3, empl, '100')

            page3.locator('div.card-first-box_yx > div.sg-btnGrounp button').get_by_text('保存', exact=True).click()
            return True
        except Exception as e:
            print(f"审核工单 {workst} 失败: {e}")
            return False

    @step_wrapper
    def _execute_audit(self, page1, df, step, flow):
        """逐个审核工单"""
        page1.bring_to_front()
        worksts = []

        for idx in df.index:
            record = df.iloc[idx]
            workst = record['工单编号'].rstrip('超延')
            user = record['处理员']

            try:
                flag = self._audit_single_order(page1, step, workst, user)
            except Exception as e:
                print(e)
                flag = self._audit_single_order(page1, step, workst, user)

            if not flag:
                continue
            # time.sleep(1)
            worksts.append(workst)
            remote_log("APPROVE", "待办工单审核完成", batch_id=step, workst_no=workst, workst_tp='电话号码核实')

        report(step, "待办工单审核完成", flow=flow)
        # remote_log("APPROVE","待办工单审核完成",batch_id=step)
        return worksts

    @step_wrapper
    def _output_audit_result(self, df, worksts, step, flow):
        """输出审核结果"""
        df_result = df[df["工单编号"].isin(worksts)].copy()
        report(step, "工单审核完成", flow=flow)
        # remote_log("FINISH","工单审核全部完成",batch_id=step)
        desc_data(df_result)

    @staticmethod
    def run(**kwargs):
        """执行"""
        obj = Base()
        obj.main(**kwargs)

    def main(self, **kwargs):
        """
        主入口：编排所有步骤
        """
        mode = get_mode()
        flow_name = '审批工单'

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
            report(1, "浏览器已启动", flow=flow_name)

            self._login(page, step=2, flow=flow_name)

            self._switch_role(page, role="站所-全业务工单", step=3, flow=flow_name)

            page1 = self._open_digital_work_order(page, step=4, flow=flow_name)
            self._open_pending_task_page(page1, step=5, flow=flow_name)

            page2 = page1.locator("iframe[src*='/gds/fswostdmgt/pendingtask']").content_frame
            self._filter_work_type(page2, step=6, flow=flow_name)
            self._query_signed_orders(page2, page1, step=7, flow=flow_name)

            # 读取待审核数据
            df = self._load_audit_data(step=8, flow=flow_name)

            # 逐个审核
            worksts = self._execute_audit(page1, df, step=9, flow=flow_name)

            # 输出审核结果
            self._output_audit_result(df, worksts, step=10, flow=flow_name)


def main(**kwargs):
    report_all({"审批工单": [
        "浏览器后台执行",
        "登录营销2.0系统",
        "切换岗位",
        "打开全量业务工单",
        "打开待办工单页面",
        "筛选工单类型",
        "查询待办工单",
        "读取待审核工单数据",
        "逐个审核工单",
        "审核全部完成"
    ]})
    Base.run(**kwargs)
    # report_all([])


if __name__ == '__main__':
    main()
