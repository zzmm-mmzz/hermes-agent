# -*- coding:utf-8 -*-
# import re
# import time
# from contextlib import ExitStack

# from playwright.sync_api import sync_playwright

from .utils import *


class Base():
    """创建电话号码核实工单 - 查询档案电话"""

    def __init__(self):
        super().__init__()

    @step_wrapper
    def _login(self, page, step, flow):
        """登录营销2.0"""
        page.login_yx20()
        report(step, "登录营销2.0完成", flow=flow)
        # remote_log("SELECT", "登录营销2.0完成", batch_id=step)

    @step_wrapper
    def _open_360_page(self, page, step, flow):
        """打开客户360视图页面"""
        page.get_by_role("textbox", name="请输入内容").click()
        page.get_by_role("textbox", name="请输入内容").fill("客户360视图")
        # time.sleep(1)
        page.locator(".el-submenu__title").click()
        page.locator("div").filter(has_text=re.compile(r"^客户信息$")).nth(1).click()
        page.get_by_text("客户360视图").click()
        report(step, "打开客户360视图完成", flow=flow)
        # remote_log("SELECT", "打开客户360视图完成", batch_id=step)

    @step_wrapper
    def _query_phone(self, page, cons_no, phone_num, step, flow):
        """查询单个用户的档案电话并与新号码比对"""
        page.locator('span.menu-item-title[title="客户360视图"]').click()
        # time.sleep(1)

        iframe = page.locator("iframe[src*='/custmgt/cust360viewplus/diansouViews']").content_frame
        search_box = iframe.get_by_role("textbox", name=re.compile(r"输入客户编号"))
        search_box.click()
        report(step, f"正在查询用户编号【{cons_no}】", flow=flow)
        # remote_log("SELECT", f"正在查询用户编号【{cons_no}】", batch_id=step)
        search_box.fill(cons_no)
        search_box.press("Enter")
        # time.sleep(2)

        iframe.get_by_role("link", name=cons_no).click()
        # time.sleep(3)

        el = iframe.locator("a").filter(has_text="联系方式：")
        phone2 = re.sub(r'联系方式[^\d]*(\d[\d*-]+)[^\s]*', r"\1", el.text_content())

        msg = f'查询到用户档案电话是【{phone2}】,待核实电话号码是【{phone_num}】。'
        print(msg)

    @staticmethod
    def run(**kwargs):
        """执行"""
        obj = Base()
        obj.main(**kwargs)

    def main(self, **kwargs):
        """
        主入口：编排所有步骤
        """
        flow_name = '查询档案内电话'
        mode = get_mode()
        cons_no = kwargs.get('cons_no', '')
        phone_num = kwargs.get('phone', '')

        if mode == '0':
            active()

        if not cons_no or not phone_num:
            print("错误：缺少用电户编号(cons_no)或电话号码(phone)参数")
            return

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
            self._open_360_page(page, step=3, flow=flow_name)
            self._query_phone(page, cons_no, phone_num, step=4, flow=flow_name)
            report(5, "查询完成", flow=flow_name)
            # remote_log("FINISH", "查询完成", batch_id=5)


def main(**kwargs):
    report_all({"查询档案内电话": [
        "浏览器后台执行",
        "登录营销2.0",
        "打开360页面",
        "查询档案电话",
        "完成"
    ]})
    Base.run(**kwargs)
    # report_all([])


if __name__ == '__main__':
    main()
