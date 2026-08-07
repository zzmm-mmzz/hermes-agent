# -*- coding:utf-8 -*-
# import re
# import os
import numpy as np
# import pandas as pd
# from contextlib import ExitStack
# from playwright.sync_api import sync_playwright
from .utils import *


class Base():

    def __init__(self):
        pass

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
        """登录营销2.0（ISC SSO 模式）"""
        page.login_isc_sso(service_url="http://hnyx2scp.hn.sgcc.com.cn:80/emss-coc-userauth-subdomain/open/login")
        report(step, "登录营销2.0完成", flow=flow)
        # remote_log("SELECT","登录营销2.0完成",batch_id=step)
        # 否则无法点击切换岗位
        try:
            page.wait_for_timeout(1000)
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
            page.keyboard.press("Escape")
        except Exception:
            pass

    @step_wrapper
    def _open_digital_workstation(self, page, step, flow):
        """打开数字化供电所（全业务工单）系统（当前标签页打开）"""
        page.get_by_role("textbox", name="请输入内容").click()
        page.get_by_role("textbox", name="请输入内容").fill("数字化供电所")
        # page.wait_for_timeout(500)
        page.locator("div.el-submenu__title").get_by_text('数字化运营').click()
        # page.wait_for_timeout(1000)

        # 如果移除 target 后仍然弹新标签页（通过 window.open），则拦截并关闭
        with page.page.context.expect_page() as new_page_info:
            page.get_by_text("数字化供电所（全业务工单）").click()
        page1 = new_page_info.value

        report(step, "打开数字化供电所（全业务工单）系统完成", flow=flow)
        # remote_log("SELECT","打开数字化供电所（全业务工单）系统完成",batch_id=step)
        return page1

    @step_wrapper
    def _open_work_pool(self, page1, step, flow):
        """打开主动工单池"""
        page1.get_by_role("textbox", name="请输入内容").click()
        page1.get_by_role("textbox", name="请输入内容").fill("主动工单池")
        page1.get_by_text("业务工单管理").click()
        page1.get_by_text("工单创建").click()
        page1.get_by_text("主动工单池").click()
        report(step, "打开主动工单池完成", flow=flow)
        # remote_log("SELECT","打开主动工单池完成",batch_id=step)

    @step_wrapper
    def _import_work_orders(self, page1, step, flow):
        """批量导入工单"""
        df0 = pd.read_excel("待建工单.xlsx")
        if not df0.empty:
            # 调试阶段只实际创建三条工单
            df0 = df0.iloc[:3, :].copy()
            # 调试
            if USERNAME == 'yiwy1':
                df0["处理人isc账号"] = "yiwy1"
            df0.to_excel("待建工单.xlsx", index=False)

            page2 = page1.locator("iframe[src*='/gds/fswoctrl/initiativeWorkPool']").content_frame

            page2.get_by_role("button", name="批量导入").click()
            # page1.wait_for_timeout(1000)
            with page1.expect_file_chooser() as fc_info:
                page2.locator('button i.sgicon-shangchuan2').click()
                file_chooser = fc_info.value
                file_chooser.set_files("待建工单.xlsx")
                page1.wait_for_timeout(3000)

            page2.locator('div[role="dialog"] button span').get_by_text('提交').click()

            # page1.wait_for_timeout(1000)

            page2.locator('div.el-message-box button span').get_by_text('确定').click()

            report(step, "工单批量导入完成", flow=flow)
            # remote_log("BATCH_CREATE","工单批量导入完成",batch_id=step)
        return df0

    @step_wrapper
    def _get_work_result(self, page1, step, flow):
        """获取工单导入结果"""
        page2 = page1.locator("iframe[src*='/gds/fswoctrl/initiativeWorkPool']").content_frame
        message = page2.locator('div.el-message-box__message p div').text_content()
        worksts = re.findall('([a-zA-Z0-9]{10,})', message)
        # page1.wait_for_timeout(1000)
        
        arr = np.array(worksts)
        arr = arr.reshape(-1, 1)
        df = pd.DataFrame(arr)
        df.columns = ["工单编码"]

        desc_data(df)
        # page1.wait_for_timeout(1000)
        report(step, "工单创建完成", flow=flow)
        for workst_no in worksts:
            remote_log("BATCH_CREATE","工单创建完成",batch_id=step,workst_no=workst_no,workst_tp='现场电费催缴')
        print("任务结束，任务成功!")

    @step_wrapper
    def _select_type(self, page1, step, flow):
        """筛选类型"""
        report(step, "正在筛选电费催收工单", flow=flow)
        # remote_log("SELECT","正在筛选电费催收工单",batch_id=step)
        # page1.wait_for_timeout(2000)
        page3 = page1.locator("iframe[src*='/gds/fswoctrl/initiativeWorkPool']").content_frame
        page3.locator('label:text("工单类型")+div input').click()
        # page1.wait_for_timeout(1000)
        page3.locator('body>div.el-cascader__dropdown span.el-cascader-node__label').get_by_text("电价电费").click()
        # page1.wait_for_timeout(1000)
        page3.locator('body>div.el-cascader__dropdown div.el-cascader-menu span.el-cascader-node__label').get_by_text('电费催收').click()
        # page1.wait_for_timeout(1000)
        page3.locator('body>div.el-cascader__dropdown div.el-cascader-menu span.el-cascader-node__label').get_by_text('现场电费催缴').click()
        # page1.wait_for_timeout(1000)
        page3.locator('div.form-item button span').get_by_text('查询', exact=True).click()
        # page1.wait_for_timeout(30*1000)
        report(step, "电费催收筛选完成", flow=flow)
        # remote_log("SELECT","电费催收筛选完成",batch_id=step)

    @staticmethod
    def run(**kwargs):
        """执行"""
        obj = Base()
        obj.main(**kwargs)

    @staticmethod
    def run_browser(**kwargs):
        """打开工单清单"""
        obj = Base()
        obj.browser_workst(**kwargs)

    @step_wrapper
    def _check_work_file(self, step, flow):
        """检查费控用户欠费明细.xlsx是否存在且非空"""
        if not os.path.exists("费控用户欠费明细.xlsx"):
            print("费控用户欠费明细.xlsx 不存在，不执行导入")
            desc_data(new_df("工单编码"))
            report(step, "任务结束", flow=flow)
            # remote_log("FINISH","检查工单文件-文件不存在",batch_id=step)
            return False
        df = pd.read_excel("费控用户欠费明细.xlsx")
        if df.empty:
            print("费控用户欠费明细.xlsx 为空文件，不执行导入")
            desc_data(new_df("工单编码"))
            report(step, "任务结束", flow=flow)
            # remote_log("FINISH","检查工单文件-文件为空",batch_id=step)
            return False
        return True

    def _gen_excel(self, filename, step, flow):
        """
        生成待建工单
        """
        df = pd.read_excel(filename)
        df = df[["序号",	"*工单类型", "工单名称", "工单时限",	"时限单位",	"自然日/工作日",	"*工单内容",	"工单对象地址",	"工单对象类型",	"业务编号",	"处理人isc账号"]].copy()
        df.to_excel("待建工单.xlsx",index=False)

        report(step, "已生成待建工单", flow=flow)
        # remote_log("EDIT","已生成待建工单",batch_id=step)


    def _launch_browser(self, mode, stack):
        """启动浏览器"""
        p1 = stack.enter_context(sync_playwright())
        browser = p1.chromium.launch(executable_path=r'C:\.hermes\chromium\chrome.exe', headless=(mode=='1'),
            args=[
                '--disable-features=Translate',
                '--disable-translate',
                '--no-first-run',
                '--no-default-browser-check',
                "--start-maximized"
            ])
        return browser

    def _launch_browser2(self, mode, stack):
        """启动浏览器,不关闭"""
        self.new_browser()

        p1 = sync_playwright().start()
        return p1.chromium.connect_over_cdp("http://127.0.0.1:19222")

    def new_browser(self):
        """
        起一个独立浏览器
        """
        import subprocess
        import winreg
        import os
        time.sleep(1)
        os.system("""
        for /f "tokens=5" %a in ('netstat -ano^| findstr :19222') do taskkill /F /PID %a
        """)
        time.sleep(1)
        chrome_path = r'C:\.hermes\chromium\chrome.exe'
        data_path = r'C:\.hermes\Chrome'

        # 启动前删除 Chrome 用户数据目录
        if os.path.exists(data_path):
            try:
                import shutil
                shutil.rmtree(data_path)
            except Exception:
                pass

        from .utils import ISC_SSO_URL
        subprocess.Popen(
            [
                chrome_path,"--remote-debugging-port=19222",
                f"--user-data-dir={data_path}",
                '--disable-features=HttpsOnlyMode',
                '--disable-features=HttpsUpgrades',
                '--disable-features=HttpsOnlyImages',
                '--disable-features=Translate',
                '--disable-translate',
                '--no-first-run',
                '--no-default-browser-check',
                "--start-maximized",
                "--disable-session-crashed-bubble",
                # "--ignore-certificate-errors",
                "--allow-running-insecure-content",
                '--disable-component-update',
                '--enable-features=  NetworkService',
                "--unsafely-treat-insecure-origin-as-secure=http://hnyx2.hn.sgcc.com.cn,http://hnyx2scp.hn.sgcc.com.cn",
                # "--disable-password-manager-reauthentication",
                # '--disable-prompt-on-repost',
            ]
        )
        time.sleep(2)

    def browser_workst(self, **kwargs):
        """主动工单池浏览入口：只编排，不写业务逻辑"""
        mode = get_mode()
        flow = '列出工单'
        message = kwargs.get('message', '【工单内容】\n该用户实时欠费大于预警金额，需催费。\n【处理要求】\n用户交清欠费才可回单，如有特殊情况需说明并附相关佐证材料。')

        active()

        with ExitStack() as stack:

            browser = self._launch_browser2(mode, stack)
            page = YX20(browser,tp=2)
            page.new_context2()
            report(1, "浏览器启动完成",flow=flow)
            # remote_log("SELECT","浏览器启动完成",batch_id=1)
            self._login(page, step=2, flow=flow)
            page.page.wait_for_timeout(7000)
            self._switch_role(page, role="站所-全业务工单", step=3, flow=flow)
            page1 = self._open_digital_workstation(page, step=4, flow=flow)
            self._open_work_pool(page1, step=5, flow=flow)
            self._select_type(page1, step=6, flow=flow)
            report(7, "完成", flow=flow)
            # remote_log("FINISH","完成任务",batch_id=7)

    def main(self, **kwargs):
        """主入口：只编排，不写业务逻辑"""
        mode = get_mode()
        flow_name = '新建工单'
        message = kwargs.get('message', '【工单内容】\n该用户实时欠费大于预警金额，需催费。\n【处理要求】\n用户交清欠费才可回单，如有特殊情况需说明并附相关佐证材料。')

        if not self._check_work_file(step=7, flow=flow_name):
            return

        if mode == '0':
            active()

        with ExitStack() as stack:
            browser = self._launch_browser(mode, stack)
            page = YX20(browser)
            report(1, "浏览器启动完成",flow=flow_name)
            # remote_log("SELECT","浏览器启动完成",batch_id=1)
            self._login(page, step=2,flow=flow_name)
            self._switch_role(page, role="站所-全业务工单", step=3,flow=flow_name)
            page1 = self._open_digital_workstation(page, step=4,flow=flow_name)
            self._open_work_pool(page1, step=5,flow=flow_name)
            self._gen_excel(filename="费控用户欠费明细.xlsx",step = 6,flow=flow_name)
            self._import_work_orders(page1, step=7,flow=flow_name)
            self._get_work_result(page1, step=8,flow=flow_name)
            report(9,"完成",flow=flow_name)
            # remote_log("FINISH","新建工单流程完成",batch_id=9)
            
            
def main(**kwargs):
    report_all({"新建工单":['浏览器后台运行中', '登录系统', '切换岗位', '打开全量业务工单', '打开主动工单池', '生成待建工单','工单批量导入','生成工单列表','任务结束']})
    Base.run(**kwargs)
    # report_all([])

def browser_workst(**kwargs):
    report_all({"列出工单":['浏览器后台运行中', '登录系统', '切换岗位', '打开全量业务工单', '打开主动工单池', '工单筛选', '任务结束']})
    Base.run_browser(**kwargs)
    # report_all([])

if __name__ == '__main__':
    main()
