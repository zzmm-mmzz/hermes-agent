import sys
import re
import time
import ctypes
import win32api
import win32con
from abc import ABC, abstractmethod

from base64 import b64encode

import argparse
from contextlib import ExitStack

# Playwright 同步 API
from playwright.sync_api import Playwright, sync_playwright, expect

from .utils import *


class Base():

    def __init__(self):
        pass

    @staticmethod
    def run(**kwargs):
        """
        执行
        """
        # active()
        obj = Base()
        obj.main(**kwargs)


    def main(self,**kwargs):
        """
        主入口
        """
        mode = kwargs.get('mode','1')
        tf_val = kwargs.get('val')  # 计划时限
        tf_unit = kwargs.get('unit')  # 计划时限
        trigger_dt = kwargs.get('dt')  # 触发时间

        if trigger_dt is None and ((tf_val is None) or (tf_unit is None)):
            print("未修改")
            return
        

        with ExitStack() as stack:
            p1 = stack.enter_context(sync_playwright())
			
            browser = p1.chromium.launch_persistent_context(executable_path = r'C:\.hermes\chromium\chrome.exe',headless=(mode=='1'),
            args=[
                '--disable-features=Translate',
                '--disable-translate',
                '--no-first-run',
                '--no-default-browser-check',
                "--start-maximized"
            ],
            user_data_dir=r"C:\.hermes\Chrome"
            )

            page = Browser(browser) # 需要打开几个网站，实例化几个page1,page2,page3 ...

            """ 代码粘贴到此处 """
            page.goto(f"{YX20_SYS_URL}/cmn/login")
			
            report(1 , "浏览器打开成功")

            lf = page.locator('#loginFrame').content_frame
            lf.locator('body input#user_tag').fill(USERNAME)
            lf.locator('body input#user_pd').fill(PASSWORD)
            lf.locator('body button#submi').click()
            time.sleep(2)
            try:
                page.locator('body input#user_tag').fill(USERNAME)
                time.sleep(1)
                page.locator('body input#user_pd').fill(PASSWORD)
                time.sleep(1)
                page.locator('body button#submi').click()
                time.sleep(5)
            except:
                pass

            time.sleep(2)

            page.get_by_text(USERNAME).click()
            time.sleep(1)
            page.get_by_text("切换岗位").click()
            time.sleep(1)
            page.get_by_text("站所-全业务工单").click()
            time.sleep(1)

            report(2 , "切换岗位-站所-全业务工单完成")


            page.get_by_role("textbox", name="请输入内容").click()
            page.get_by_role("textbox", name="请输入内容").fill("数字化供电所")
            page.locator(".el-submenu__title").click()
            with page.expect_popup() as page1_info:
                page.get_by_text("数字化供电所（全业务工单）").click()
            page1 = page1_info.value

            report(3 , "打开数字化供电所（全业务工单）完成")
            page1.get_by_role("textbox", name="请输入内容").click()
            page1.get_by_role("textbox", name="请输入内容").fill("计划自动生成规则管理")
            page1.get_by_text("基础管理").click()
            page1.get_by_text("计划配置").click()
            page1.get_by_text("计划自动生成规则管理").click()
            time.sleep(1)
            report(4 , "打开计划自动生成规则管理完成")


            # page.page.pause()

            page1.set_viewport_size({"width":1920,"height":1080})
            time.sleep(1)

            page2 = page1.locator("iframe[src*='/gds/fswosmartrule/planRule']").content_frame
            # page.page.pause()
            page2.locator('label[for=ruleName]+div input').click()
            # page2.get_by_role("textbox", name="请输入").click()
            page2.locator('label[for=ruleName]+div input').fill('月电费催缴')

            page2.get_by_role("button", name="查询").click()
            time.sleep(3)
            report(5 , "查询月电费催缴完成")

            page2.locator('div.card-first-box_yx div.card-second-box_yx div.card-third-box_yx div.list-box div.el-table__fixed-right table tr td button').get_by_text('修改').first.click() # 选第一条数据

            if trigger_dt:
                # 处理时间部分，未来可以复用
                page2.locator('div[title=触发时间] input').click() # 点击触发时间
                time.sleep(1)
                page2.locator("div.dialog-inner input[placeholder='']").click()  # 时间
                time.sleep(1)

                h,m,s = list(page2.locator('div.el-time-panel div.has-seconds ul').all()) # 时分秒

                trigger_dt = trigger_dt + ' 00:00:00'
                dt,tm = trigger_dt.split(' ')[:2]
                # tm = '01:12:23' # 用户输入
                hv,mv,sv = tm.split(':')
                h.locator('li').get_by_text(hv).click() # 时
                m.locator('li').get_by_text(mv).click() # 分
                s.locator('li').get_by_text(sv).click() # 秒

                page2.locator('div.el-time-panel button.el-time-panel__btn').get_by_text('确定').click() # 确定
                time.sleep(1)
                page2.locator("div.dialog-inner input[placeholder='请选择']").click()  # 日期
                time.sleep(1)
                # dt = '2026-06-02' # 日期 用户输入
                dv = int(dt.strip()[-2:])
                dvs = f"{dv}号"
                page2.locator('div.el-time-panel+div ul li span').get_by_text(dvs,exact=True).click()
                time.sleep(1)
                page2.locator("div.dialog-inner button").get_by_text('保存').click()

                # 处理时间部分，未来可以复用

            if tf_val and tf_unit:

                # 计划时间
                page2.locator('div[title="计划时限"] input[title]').click()
                page2.locator('div[title="计划时限"] input[title]').fill(f"{tf_val}")
                time.sleep(1)
                page2.locator('div[title="计划时限"] i.el-select__caret').click() #选择天或者小时  tf_unit
                time.sleep(1)
                assert tf_unit in ["天","小时"],f"{tf_unit} 只能是天或者小时"
                page2.locator('body>div.el-select-dropdown ul.el-select-dropdown__list li.el-select-dropdown__item span').get_by_text(f'{tf_unit}').click() # 小时/天

                time.sleep(1)

            page2.locator('div[aria-label=计划自动生成规则] div.sg-btnGrounp-dialog button').get_by_text('确定').click()

            time.sleep(1)

            report(6 , "任务结束")

            print('修改完成')


def main(**kwargs):
    report_all(['浏览器后台运行中', '切换岗位-站所-全业务工单', '打开数字化供电所（全业务工单）', '打开计划自动生成规则管理', '查询月电费催缴', '任务结束'])
    Base.run(**kwargs)
    report_all([])

if __name__ == '__main__':
    main()
