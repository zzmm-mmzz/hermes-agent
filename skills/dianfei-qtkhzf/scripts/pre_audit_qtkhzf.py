# -*- coding:utf-8 -*-
# import re
# import time
# import pandas as pd
# from io import StringIO
# from contextlib import ExitStack

# from playwright.sync_api import sync_playwright

from .utils import *


class Base():
    """待审批工单清单查询"""

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
        """打开待办工单列表页面"""
        page1.get_by_role("textbox", name="请输入内容").click()
        # time.sleep(1)
        page1.get_by_role("textbox", name="请输入内容").fill("待办工单")
        # time.sleep(1)
        page1.locator("div.navMenu div.el-submenu__title span.second-sub-title").get_by_text("业务工单管理").click()
        # time.sleep(1)
        page1.locator("div.navMenu div.el-submenu__title span.second-sub-title").get_by_text("工单管理", exact=True).click()
        # time.sleep(2)
        page1.get_by_text("待办工单").click()
        # time.sleep(1)
        report(step, "已打开待办工单列表页面", flow=flow)
        # remote_log("SELECT","已打开待办工单列表页面",batch_id=step)

    @step_wrapper
    def _filter_by_work_type(self, page2, page1, step, flow):
        """按工单类型筛选-客户其他服务工单"""
        page2.get_by_title("工单类型").locator("i").click()
        # time.sleep(1)
        page2.get_by_role("textbox", name="请输入关键字过滤").click()
        # time.sleep(1)
        page2.get_by_role("textbox", name="请输入关键字过滤").fill("客户其他服务工单")
        page2.locator("span.el-tree-node__label").get_by_text('客户其他服务工单').wait_for(state='visible', timeout=5000)
        page2.locator("span.el-tree-node__label").get_by_text('客户其他服务工单', exact=True).click()
        # time.sleep(1)
        page2.get_by_role("button", name="保存").click()
        # time.sleep(1)
        report(step, "已筛选【客户其他服务工单】工单类型", flow=flow)
        # remote_log("SELECT","已筛选【客户其他服务工单】工单类型",batch_id=step)

    @step_wrapper
    def _signin_work_orders(self, page2, page1, step, flow):
        """签收未处理的其他客户走访工单"""
        try:
            # 筛选未签收
            page2.locator('label[for=workItemStat]+div input').click()
            # time.sleep(1)
            page2.locator('ul.el-select-dropdown__list li.el-select-dropdown__item span').get_by_text('未签收', exact=True).click()
            # time.sleep(1)

            # 切换分页大小为50
            page2.locator('span.el-pagination__sizes input').click()
            page2.locator('body > div.el-select-dropdown ul.el-select-dropdown__list li.el-select-dropdown__item span').get_by_text('条/页').get_by_text('50').click()
            # page1.wait_for_load_state('networkidle')
            report(step, "已筛选未处理的其他客户走访工单", flow=flow)
            # remote_log("SELECT","已筛选未处理的其他客户走访工单",batch_id=step)
            # 强制等待
            time.sleep(0.5)

            try:
                page2.locator("div.card-third-box_yx div.pendingtask-table div.el-table__body-wrapper tbody tr").first.wait_for(state='visible', timeout=5000)
                records = page2.locator("div.card-third-box_yx div.pendingtask-table div.el-table__body-wrapper tbody tr").all()
                for record in records:
                    record.click()
                page2.locator('div.sg-btnGrounp button span').get_by_text('签收', exact=True).click()
                page1.wait_for_load_state('networkidle')
                report(8, "已完成目标工单的签收", flow=flow)
                # remote_log("EDIT","已完成目标工单的签收",batch_id=8)
            except Exception:
                report(8, "无目标工单可以签收", flow=flow)
        except Exception as e:
            print(f"签收工单失败: {e}")
            report(step, f"签收工单失败: {e}", flow=flow)

    @step_wrapper
    def _filter_signed_orders(self, page2, page1, step, flow):
        """筛选已签收+工单处理的工单"""
        try:
            page2.locator('label[for=workItemStat]+div input').click()
            # time.sleep(1)
            page2.locator('ul.el-select-dropdown__list li.el-select-dropdown__item span').get_by_text('已签收', exact=True).click()
            # time.sleep(1)

            page2.locator('label[for=stepName]+div input').click()
            # time.sleep(1)
            page2.locator('ul.el-select-dropdown__list li.el-select-dropdown__item span').get_by_text('工单处理', exact=True).click()
            # time.sleep(1)

            page2.get_by_role("button", name="查询").click()
            # time.sleep(1)
            page1.wait_for_load_state('networkidle')
            report(step, "已筛选出在处理环节的已签收工单", flow=flow)
            # remote_log("SELECT","已筛选出在处理环节的已签收工单",batch_id=step)
        except Exception as e:
            print(f"筛选已签收工单失败: {e}")
            report(step, f"筛选已签收工单失败: {e}", flow=flow)

    @step_wrapper
    def _download_pending_orders(self, page2, page1, step, flow):
        """下载待审核工单数据并保存到Excel"""
        df = self._download_data(page2, page1)
        df = df[['工单编号', '工作内容/作业内容', '业务名称', '处理人']].copy()
        columns = ['工单编号', '工单内容', '用户名称', '处理员']
        df.columns = columns
        df.reset_index(drop=True, inplace=True)
        df['序号'] = df.index.map(lambda x: x + 1).astype('str')
        df = df[['序号'] + columns].copy()
        df['工单编号'] = df['工单编号'].map(lambda x: re.sub(r'[^^a-zA-Z0-9]', '', x))
        df.to_excel('待审核工单.xlsx', index=False)
        desc_data(df)
        report(step, "待审核工单导出完成", flow=flow)
        # remote_log("EXPORT","待审核工单导出完成",batch_id=step)

    def _download_data(self, page2, page1):
        """导出工单数据"""
        try:
            def get_data(p):
                page2.locator('span.el-pagination__jump div input').fill(f'{p}')
                page2.get_by_role("button", name="查询").click()
                page1.wait_for_load_state('networkidle')
                temp = page2.locator('div.el-table__body-wrapper').evaluate("el => el.innerHTML")
                stream = StringIO(temp)
                return pd.read_html(stream, flavor='lxml')[0]

            size_text = page2.locator('span.el-pagination__total').text_content()
            size = int(re.findall(r'(\d+)', size_text)[0])

            headers = [x.text_content().strip() for x in page2.locator('div.el-table__header-wrapper th').all()]
            if headers and headers[-1].strip() == "":
                headers = headers[:-1]

            columns = ["序号", "工单编号", "专业分类", "业务类型", "工作场景", "环节名称",
                       "工作内容/作业内容", "工单类型", "工单时限", "工单计划完成时间",
                       "处理人", "业务编号", "业务名称"]

            if size > 0:
                df = get_data(1)
                df.columns = headers
            else:
                df = pd.DataFrame({col: [] for col in headers})

            return df[columns].copy()
        except Exception as e:
            print(f"导出工单数据失败: {e}")
            return new_df("工单编号")



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
        flow_name = '获取待审批工单清单'

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

            # 待办工单页面
            self._open_pending_task_page(page1, step=5, flow=flow_name)

            page4 = page1.locator("iframe[src*='/gds/fswostdmgt/pendingtask']").content_frame

            # 筛选工单类型
            self._filter_by_work_type(page4, page1, step=6, flow=flow_name)

            # 签收未处理工单
            self._signin_work_orders(page4, page1, step=7, flow=flow_name)

            # 筛选已签收+工单处理
            self._filter_signed_orders(page4, page1, step=8, flow=flow_name)

            # 导出待审核工单
            self._download_pending_orders(page4, page1, step=9, flow=flow_name)


def main(**kwargs):
    report_all({"获取待审批工单清单": [
        "启动浏览器",
        "登录系统",
        "切换岗位",
        "打开全量业务工单",
        "打开待办工单列表页面",
        "筛选工单类型",
        "签收目标工单",
        "筛选已签收工单",
        "导出待审核工单"
    ]})
    Base.run(**kwargs)
    # report_all([])


if __name__ == '__main__':
    main()
