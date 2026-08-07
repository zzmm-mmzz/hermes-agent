# -*- coding:utf-8 -*-
# import re
# import time
# import pandas as pd
# from contextlib import ExitStack

# from playwright.sync_api import sync_playwright

from .utils import *


class Base():
    """派单-创建电话号码核实工单并派单"""

    def __init__(self):
        super().__init__()

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
    def _login(self, page, step, flow):
        """登录营销2.0"""
        page.login_yx20()
        report(step, "登录营销2.0完成", flow=flow)
        # remote_log("SELECT", "登录营销2.0完成", batch_id=step)

    @step_wrapper
    def _open_digital_work_order(self, page, step, flow):
        """打开数字化供电所（全业务工单）"""
        page.get_by_role("textbox", name="请输入内容").click()
        page.get_by_role("textbox", name="请输入内容").fill("数字化供电所")
        page.locator(".el-submenu__title").click()
        with page.expect_popup() as page1_info:
            page.get_by_text("数字化供电所（全业务工单）").click()

        page1 = page1_info.value
        width = win32api.GetSystemMetrics(0)
        height = win32api.GetSystemMetrics(1)
        if width <= 1920 or height <= 1080:
            width, height = 1920, 1080
        page1.set_viewport_size({"width": width, "height": height})
        report(step, "已打开全量业务工单", flow=flow)
        # remote_log("SELECT", "已打开全量业务工单", batch_id=step)
        return page1

    @step_wrapper
    def _open_initiative_work_pool(self, page1, step, flow):
        """打开主动工单池"""
        page1.get_by_role("textbox", name="请输入内容").click()
        page1.get_by_role("textbox", name="请输入内容").fill("主动工单池")
        # time.sleep(1)
        page1.get_by_text("业务工单管理").click()
        # time.sleep(1)
        page1.get_by_text("工单创建").click()
        # time.sleep(1)
        page1.get_by_text("主动工单池").click()
        # time.sleep(1)
        report(step, "已打开主动工单池", flow=flow)
        # remote_log("SELECT", "已打开主动工单池", batch_id=step)

    @step_wrapper
    def _create_new_order(self, page1, step, flow):
        """点击新建工单"""
        page2 = page1.locator("iframe[src*='/gds/fswoctrl/initiativeWorkPool']").content_frame
        # time.sleep(3)
        page2.get_by_role("button", name="新建").first.click()
        # time.sleep(6)
        report(step, "已打开工单创建页面", flow=flow)
        return page2

    @step_wrapper
    def _select_work_type(self, page3, step, flow):
        """选择工单类型：电价电费-电费管理电话号码收集-电费管理-电话号码核实"""
        page3.locator('label:text("工单类型")+div input').click()
        # time.sleep(2)

        page3.locator('body>div.el-cascader__dropdown span.el-cascader-node__label').get_by_text("电价电费").click()
        # time.sleep(1)
        page3.locator('body>div.el-cascader__dropdown div.el-cascader-menu span.el-cascader-node__label').get_by_text('电费管理电话号码收集').click()
        # time.sleep(1)
        page3.locator('body>div.el-cascader__dropdown div.el-cascader-menu span.el-cascader-node__label').get_by_text('电费管理-电话号码核实').click()
        # time.sleep(1)

        # 选择工单对象类型为"用户"
        page3.locator("text=工单对象类型").locator("..").locator("role=textbox").click()
        page3.locator("li.el-select-dropdown__item").get_by_text("用户", exact=True).click()
        # time.sleep(1)

        report(step, "完成工单类型及对象类型选择", flow=flow)
        # remote_log("SELECT", "完成工单类型及对象类型选择", batch_id=step)

    @step_wrapper
    def _select_customer(self, page3, cons_no, step, flow):
        """选择客户对象"""
        page3.locator('div[title="用户编号"]+div span.sgicon-list').click()
        dialog = page3.locator("div:has-text('客户查询')")

        # 输入用电户编号
        page3.locator('div[title="用电户编号"] input').click()
        page3.locator('div[title="用电户编号"] input').fill(cons_no)
        # time.sleep(1)

        # 点击查询
        query_button = dialog.get_by_role("button", name="查询")
        query_button.click()
        # time.sleep(4)

        # 选择查到的用户
        try:
            page3.locator('div.dialog-inner div.dialog-body div.table-box div.el-table__body-wrapper tbody tr').nth(0).click()
        except Exception as e:
            print(f"{cons_no} 未找到用户，请检查该用户是否属于当前供电所。")
            raise RuntimeError(f"未找到用户 {cons_no}") from e

        cons_nm = page3.locator(
            'div.dialog-inner div.dialog-body div.table-box div.el-table__body-wrapper tbody tr .el-table_2_column_10 div'
        ).nth(0).text_content()

        # time.sleep(3)
        dialog.locator("button.el-button--primary", has_text="确定").click()
        # time.sleep(1)

        report(step, f"完成客户选择-{cons_nm}", flow=flow)
        # remote_log("SELECT", f"完成客户选择-{cons_nm}", batch_id=step)
        return cons_nm

    @step_wrapper
    def _fill_work_content(self, page3, cons_no, cons_nm, phone, doc_phone, step, flow):
        """填写工单内容并保存"""
        order_text = """ 【工单内容】
        用户{cons_nm}电话号码异常，请核实该户绑定的联系电话是否需要新增或变更至{phone}（原绑定的联系电话为{doc_phone}），如需变更或新增联系电话，同步收集客户证件信息
        【处理要求】
        1.无需变更：因系统号码为自家号码（{doc_phone}），无需变更；
        2.需要变更：XX月XX日已与{phone}绑定；；
        3.推广属地电话、一户一贴、客户入社群等；
        4.提供正确电话号码收集的佐证。"""
        work_order_content = order_text.format(cons_nm=cons_nm, phone=phone, doc_phone=doc_phone)
        page3.locator('div[title="工单内容"] textarea').click()
        page3.locator('div[title="工单内容"] textarea').fill(work_order_content)
        # time.sleep(2)

        save_button = page3.get_by_role("button", name="保存")
        save_button.click()
        # time.sleep(2)
        report(step, "完成工单内容填写并保存工单", flow=flow)
        # remote_log("CREATE", "完成工单内容填写并保存工单", batch_id=step)
        # time.sleep(3)

    @step_wrapper
    def _assign_handler(self, page3, page1, empl, step, flow):
        """选择工单处理人并提交"""
        page3.locator('div[title=工单处理人] input').click()  # 点击工单处理人
        page3.locator('div.dialog-left span.el-pagination__sizes input').click()  # 分页
        page3.locator('body>div.el-select-dropdown li.el-select-dropdown__item span:text("条/页")').get_by_text('50条/页').click()
        # time.sleep(2)

        # 列出所有的工单处理人进行选择
        records = page3.locator('div.dialog-inner div.dialog-body div.table-box div.el-table__body-wrapper tbody tr').all()
        users = []
        for record in records:
            vals = [x.text_content() for x in record.locator('td').all()]
            users.append(vals[4])

        if users.count(empl):
            idx = users.index(empl)
        else:
            print(f'处理人{empl}不在处理人清单中')
            return None

        records[idx].click()
        # time.sleep(2)
        page3.locator('div.sg-btnGrounp-dialog button').get_by_text('保存').click()
        # time.sleep(1)
        report(step, "完成工单处理人选择", flow=flow)
        # remote_log("EDIT", "完成工单处理人选择", batch_id=step)

        # 提交工单
        page3.locator('div.card-first-box_yx div.sg-btnGrounp-right button span').get_by_text('提交').click()
        # time.sleep(2)

        # 获取工单编号
        el = page1.locator("iframe[src*=workOrderCreate]:not([style*=display])").content_frame.locator(
            "form div.form-item div[title=工单编号] input"
        )
        title = el.get_attribute("title")
        # time.sleep(2)

        page3.locator('div[role="dialog"] div.el-message-box button span').get_by_text('是').click()
        # time.sleep(1)
        report(step+1, "完成电话号码核实工单创建", flow=flow)
        remote_log("CREATE", "完成电话号码核实工单创建", batch_id=step+1, workst_no=title, workst_tp='电话号码核实')
        # time.sleep(1)
        print(f"电话号码核实工单已创建{title}")

        return title

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
        flow_name = '创建电话号码核实工单'
        cons_no = kwargs.get('cons_no', '')
        empl = kwargs.get('empl', '')
        phone = kwargs.get('phone', '')
        doc_phone = kwargs.get('doc_phone', '')

        if not cons_no or not empl or not phone or not doc_phone:
            print("错误：缺少用电户编号、接单人、待核实电话、档案电话参数")
            return

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
            page1 = self._open_digital_work_order(page, step=4, flow=flow_name)
            self._open_initiative_work_pool(page1, step=5, flow=flow_name)

            page2 = self._create_new_order(page1, step=6, flow=flow_name)

            # 工单创建页面的 iframe
            page3 = page1.locator('iframe[src*="/gds/fswoctrl/workOrderCreate"]').content_frame

            self._select_work_type(page3, step=7, flow=flow_name)
            cons_nm = self._select_customer(page3, cons_no, step=8, flow=flow_name)
            self._fill_work_content(page3, cons_no, cons_nm, phone, doc_phone, step=9, flow=flow_name)

            title = self._assign_handler(page3, page1, empl, step=10, flow=flow_name)
            if title is None:
                return

            # 输出结果
            df = pd.DataFrame([[title, cons_nm, empl]], columns=["工单编号", "用户名称", "接单人员"])
            desc_data(df)

            report(11, "完成", flow=flow_name)


def main(**kwargs):
    report_all({"创建电话号码核实工单": [
        "启动浏览器",
        "登录系统",
        "切换岗位",
        "打开全量业务工单",
        "打开主动工单池",
        "打开工单创建页面",
        "选择工单类型、对象类型",
        "选择客户",
        "填写工单内容、保存工单",
        "选择工单处理人",
        "创建工单"
    ]})
    Base.run(**kwargs)
    # report_all([])


if __name__ == '__main__':
    main()