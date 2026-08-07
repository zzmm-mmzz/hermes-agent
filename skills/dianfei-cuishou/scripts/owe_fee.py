# -*- coding:utf-8 -*-

# import re
from base64 import b64encode
# import ctypes

# from lxml import etree
# import csv
# from io import StringIO

# import argparse

# from contextlib import ExitStack

import pandas as pd 

# Playwright 同步 API
# from playwright.sync_api import Playwright, sync_playwright, expect      

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
    def _open_owe_query_page(self, page, step, flow):
        """打开费控欠费客户情况查询页面"""
        page.navigate_menu2('费控欠费客户情况查询', ['计费结算', '支付结算', '费控管理', '费控工作台', '费控查询', '费控用户情况查询', {'menu_item_title': '费控欠费客户情况查询'}])
        report(step, "打开费控欠费客户情况查询完成",flow=flow)
        # remote_log("SELECT","打开费控欠费客户情况查询完成",batch_id=step)

    def _get_page_data(self, page, page2, page_num, step, flow):
        """翻页获取指定页的数据
        Args:
            page: 顶层 page 对象
            page2: iframe 内页面对象
            page_num: 页码
        """
        try:
            # page.page.wait_for_timeout(15000)
            report(step,f'正在获取第{page_num}页数据',flow=flow)
            # remote_log("SELECT",f'正在获取第{page_num}页数据',batch_id=step)

            page2.locator('span.el-pagination__jump div input').fill(f'{page_num}')
            page2.locator('span.el-pagination__jump div input').press("Enter")
            self._wait_loading_done(page.page, page2, timeout=60000,step = step,flow=flow) # 等待加载中结束
            page.page.wait_for_load_state('domcontentloaded')
            page.page.wait_for_timeout(2000) # 保证数据已经变化

            for _ in range(60):
                page2.locator('div.el-table__body-wrapper tr').first.wait_for(state='visible', timeout=15000)
                temp = None
                try:
                    temp = page2.locator('div.el-table__body-wrapper').evaluate("el => el.innerHTML")
                except Exception:
                    temp = None
                    continue
                break
            try:
                result = pd.read_html(StringIO(temp), flavor='lxml')[0]
                return result
            except Exception as e:
                # print(f'第{page_num}页解析失败：{e}，跳过')
                report(step,f'第{page_num}页解析失败：{e}，跳过',flow=flow)
                # remote_log("SELECT",f'第{page_num}页解析失败：{e}，跳过',batch_id=step)
                
                return
        except Exception as e:
            print(f'第{page_num}页获取数据失败: {e}')

            report(step, f'第{page_num}页获取数据失败: {e}',flow=flow)
            # remote_log("SELECT",f'第{page_num}页获取数据失败: {e}',batch_id=step)

    @step_wrapper
    def _set_query_condition(self, page, step, flow):
        """设置查询条件并点击查询"""
        page2 = page.locator("iframe[src*='/bus/expusesitquey/feeControlOverCus']").content_frame
        # page.page.wait_for_timeout(1000)
        # -10以下用户
        page2.locator('div[title="可用余额区间"] input').nth(1).fill('-10')

        # 已全部停电用户
        page2.locator('div[title="欠费停复电状态"] input').click()
        page2.get_by_text("已全部停电").click()

        """ 只查3条，暂不翻页
        page2.locator('span.el-pagination__sizes input').click()  # 分页
        page2.locator('body>div.el-select-dropdown div.el-scrollbar ul li').filter(has_text='20条/页').first.wait_for(state='visible', timeout=5000)
        page2.locator('body>div.el-select-dropdown div.el-scrollbar ul li').get_by_text('条/页').get_by_text('20').click()
        self._wait_loading_done(page.page,page2,timeout=90000, step=step,flow=flow)
        """

        report(step,"查询条件配置完成",flow=flow)
        # remote_log("SELECT",'查询条件配置完成',batch_id=step)

    @step_wrapper
    def _export_owe_data(self, page, step, flow):
        """查询并导出费控欠费用户数据"""
        # page.wait_for_timeout(3000)
        page2 = page.locator("iframe[src*='/bus/expusesitquey/feeControlOverCus']").content_frame
        page2.get_by_role("button", name="查询").click()
        self._wait_loading_done(page.page,page2, timeout=60000, step=step,flow=flow)  # 加载中
        # page.page.wait_for_timeout(15000)
        page.page.wait_for_load_state('domcontentloaded')
        # page.page.wait_for_timeout(2000)
        # 等待查询结果加载完成（表格总记录数出现）
        page2.locator('span.el-pagination__total').wait_for(state='visible', timeout=90000)
        size = page2.locator('span.el-pagination__total').text_content()
        size = int(re.findall(r'(\d+)', size)[0])

        if size > 0:
            page_nums = [x+1 for x,y in enumerate(list(range(0,size,20)))][:5] # 最多取5页

            headers = [x.text_content().strip() for x in page2.locator('div.el-table__header-wrapper th').all()]

            # 直接读取当前第1页数据，不触发翻页
            stream = StringIO(page2.locator('div.el-table__body-wrapper').inner_html())
            df_main = [pd.read_html(stream, flavor='lxml')[0]]

            # dfs = map(lambda x:self._get_page_data(page,page2,x,step=step,flow=flow),page_nums[1:])  # 第一页不用翻页
            dfs = map(lambda x:self._get_page_data(page,page2,x,step=step,flow=flow),page_nums[:0])  # 暂只看第一页

            df_list = list(dfs)
            df = pd.concat([*df_main, *df_list])
            if headers[-1].strip() == "":
                headers = headers[:-1]

            df.columns = headers
            df["用户编号"] = df["用户编号"].astype("str")
            df.to_excel('费控用户欠费明细-全部.xlsx', index=False)

            print('数据导出完成')
            report(step, "费控欠费用户数据导出完成",flow=flow)
        else:
            self._export_empty_owe_data(step,flow=flow)

    @step_wrapper
    def _export_empty_owe_data(self, step, flow):
        """查询无结果时导出空Excel（空数据分支）"""
        columns = ["序号", "供电单位", "抄表包编号", "催费员", "客户类型", "抄表段名称", "用户编号", "用户名称", "用电地址", "联系电话", "是否可停电", "测算日期", "测算电量", "测算电费", "月结余额", "可用余额", "缴费方式", "最近一次缴费时间", "基准策略", "预警最近一次发送时间", "回执状态", "回执内容", "欠费停复电状态"]
        df = pd.DataFrame(columns=columns)
        df.to_excel('费控用户欠费明细-全部.xlsx', index=False)
        report(step, "费控欠费用户数据导出完成",flow=flow)

    @step_wrapper
    def _export_owe_cfy(self, page, step, flow):
        """
        获取催费员数据
        """
        page2 = page.locator("iframe[src*='/bus/expusesitquey/feeControlOverCus']").content_frame
        page2.locator('div[title="催费员"] input').click()
        # 等待催费员窗口打开
        page.wait_for_timeout(1000)
        
        headers = [x.text_content().strip() for x in page2.locator('div[role=dialog] div.p-tit:text("人员信息")+div div.el-table--fit div.el-table__header-wrapper th').all()] 
        if headers[-1].strip() == "":
            headers = headers[:-1]

        page2.locator('div[role=dialog] span.el-pagination__total').wait_for(state='visible', timeout=90000)
        size = page2.locator('div[role=dialog] span.el-pagination__total').text_content()
        size = int(re.findall(r'(\d+)', size)[0])
        if size > 0:
            page2.locator('div[role=dialog] span.el-pagination__sizes input').click() # 分页
            # page.wait_for_timeout(1000)
            page2.locator('body>div.el-select-dropdown div.el-scrollbar ul li').get_by_text('条/页').get_by_text('100').click()
            # 等待催费员加载完全
            page.wait_for_timeout(1000)

            # 直接读取当前第1页数据，不触发翻页
            stream = StringIO(page2.locator('div[role=dialog] div.p-tit:text("人员信息")+div div.el-table--fit div.el-table__body-wrapper').inner_html())
            df = pd.read_html(stream, flavor='lxml')[0]
            df.columns = headers
            df = df[["姓名","账号"]].copy()
            df.to_excel("催费员.xlsx",index=False)

        pass


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
    def run(**kwargs):
        """
        执行
        """
        obj = Base()
        obj.main(**kwargs) # 下载数据

    @step_wrapper
    def _login(self, page, step, flow):
        """登录"""
        status = page.login_yx20()
        if not status:
            report(step, "登录失败：请手动测试是否能够登录成功",flow=flow)
            raise RuntimeError("登录失败：请手动测试是否能够登录成功")
        report(step,"登录营销2.0完成",flow=flow)

    def main(self,**kwargs):
        """
        主入口
        """
        mode = get_mode()
        flow_name = '导出数据'
        flow_name2 = '数据清洗'

        if mode == '0':
            active()

        with ExitStack() as stack:
            p1 = stack.enter_context(sync_playwright())
            browser = p1.chromium.launch(executable_path = r'C:\.hermes\chromium\chrome.exe',headless=(mode=='1'),
            args=[
                '--disable-features=Translate',
                '--disable-translate',
                '--no-first-run',
                '--no-default-browser-check',
                "--start-maximized"
            ]
            )

            page = YX20(browser) # 需要打开几个网站，实例化几个page1,page2,page3 ...

            """ 代码粘贴到此处 """

            report(1 , "浏览器启动完成",flow=flow_name)
            self._login(page,step=2,flow=flow_name) #  登录营销2.0
            self._switch_role(page,role="站所-班组长-站所长",step = 3,flow=flow_name) # 切换用户角色
            self._open_owe_query_page(page,step = 4,flow=flow_name)  # 打开费控欠费客户情况查询
            self._set_query_condition(page,step = 5,flow=flow_name) # 配置查询条件
            self._export_owe_data(page, step = 6,flow=flow_name) # 读取费控用户欠费明细
            self._export_owe_cfy(page,step=7,flow=flow_name) # 获取催费员isc
            self.parse_data(filename = '费控用户欠费明细-全部.xlsx',step = 8,flow=flow_name2) # 数据清洗
            # self.desc_owe(filename = '费控用户欠费明细-初筛版.xlsx',step = 9 ,flow=flow_name2) # 数据展示  新建费控用户欠费明细-初筛版.xlsx 文件
            self.gen_workst_excel(filename = "费控用户欠费明细-初筛版.xlsx",step = 9, flow=flow_name2) # 新建待办工单
            self.desc_all(step=10,flow=flow_name2) # 展示数据

    def desc_all(self, step, flow):
        """
        合并`费控用户欠费明细-初筛版.xlsx` 与 `待建工单.xlsx`
        通过 用户编号 与 业务编号 关联
        """
        import os

        fn_detail = '费控用户欠费明细-初筛版.xlsx'
        fn_workst = '待建工单.xlsx'

        if not os.path.exists(fn_detail):
            report(step, f"文件不存在: {fn_detail}", flow=flow)
            raise FileNotFoundError(f"文件不存在: {fn_detail}")
        if not os.path.exists(fn_workst):
            report(step, f"文件不存在: {fn_workst}", flow=flow)
            raise FileNotFoundError(f"文件不存在: {fn_workst}")

        df_detail = pd.read_excel(fn_detail, dtype={"用户编号": str})
        df_workst = pd.read_excel(fn_workst, dtype={"业务编号": str})

        # 从 df_detail 中选取需要的字段，以 df_workst 为主表关联
        df_merge_cols = df_detail[["用户编号", "抄表段名称", "用户名称", "可用余额", "预警最近一次发送时间"]].copy()

        df = pd.merge(
            df_workst,
            df_merge_cols,
            left_on="业务编号",
            right_on="用户编号",
            how="left",
            suffixes=("", "_明细")
        )

        # 调整字段顺序：工单字段在前，补充字段在后
        base_cols = [c for c in df_workst.columns]
        extra_cols = ["抄表段名称", "用户名称", "可用余额", "预警最近一次发送时间"]
        ordered_cols = base_cols + extra_cols
        df = df[[c for c in ordered_cols if c in df.columns]]
        df.to_excel("费控用户欠费明细.xlsx",index=False)
        desc_data(df)
        report(step, "合并展示完成", flow=flow)

    def parse_data(self, filename, step, flow):
        """
        解析数据
        """
        df = pd.read_excel(filename, dtype={"可用余额": "float32"})

        report(step, "读取费控用户欠费明细完成",flow=flow)

        df = df[~df['基准策略'].str.contains('关联策略')].copy() # 不包含关联策略

        report(step , "剔除基准策略包含关联策略数据完成",flow=flow)
        
        #待补充 最近一次缴费时间 不是当天(当前没数据，无法添加策略)

        df.sort_values(by='可用余额', inplace=True)
        report(step , "按余额排序完成",flow=flow)
        df.reset_index(drop=True, inplace=True)
        df = df.iloc[:3, :].copy()
        report(step , "获取前3条数据完成",flow=flow)

        df['序号'] = df.index.map(lambda x:x+1)
        df["用户编号"] = df["用户编号"].astype("str")
        df.to_excel('费控用户欠费明细-初筛版.xlsx',index=False)

        report(step , "筛选欠费金额最多的3个用户完成",flow=flow)

        # 输出依据汇总语句
        total_count = len(df)
        total_owe = abs(df['可用余额'].sum())
        large_owe_count = (df['可用余额'] < -100).sum()
        # 查询条件已固定为"已全部停电"，停电户数等于总户数
        power_off_count = (df['欠费停复电状态'] == '已全部停电').sum() if '欠费停复电状态' in df.columns else total_count
        summary = f"查询到欠费用户{total_count}户，累计欠费金额{total_owe:.2f}元，欠费数额较大的用户{large_owe_count}户（欠费金额大于100），已停电用户{power_off_count}户"
        report(step, summary, flow=flow)
        # print(f"\n{'='*60}")
        print(f"{summary}")
        # print(f"{'='*60}\n")

    # 生成导入模板
    def gen_workst_excel(self, filename, step, flow):
        """
        生成导入模板
        """
        df = pd.read_excel(filename)
        df.reset_index(drop=True,inplace=True)

        report(step, "读取费控用户欠费明细数据完成",flow=flow)
        report(step, "数据清洗（过滤非欠费用户）完成",flow=flow)

        # 读取催费员映射表
        try:
            cfy_df = pd.read_excel("催费员.xlsx")
        except FileNotFoundError:
            raise FileNotFoundError("催费员.xlsx 文件不存在，请先导出催费员数据")

        name_col = cfy_df.columns[0]
        account_col = cfy_df.columns[1]
        cfy_map = dict(zip(cfy_df[name_col], cfy_df[account_col]))

        df["处理人isc账号"] = df["催费员"].map(cfy_map)
        # 去除未匹配到isc账号的数据
        before = len(df)
        df = df.dropna(subset=["处理人isc账号"]).copy()
        after = len(df)
        if before != after:
            report(step, f"已过滤 {before - after} 条未匹配到isc账号的数据",flow=flow)

        df["序号"] = df.index.map(lambda x: x + 1).astype('str')
        df["*工单内容"] = df.apply(lambda row: f"【{row['抄表段名称']}】的用户【{row['用户名称']}】已实时欠费【{abs(row['可用余额']):.2f}元】，通过智能语音催费仍未交费，需催费", axis=1)
        report(3, "工单内容生成完成")
        df["业务编号"] = df["用户编号"]
        df["工单对象类型"] = "客户"  
        df["*工单类型"] = "现场电费催缴" # 文档给的是电费，待确认
        df["工单时限"] = 3
        df["时限单位"] = "天"
        df["自然日/工作日"] = "工作日"
        df["工单对象地址"] = df["用电地址"]
        df["工单名称"] = "电费催收"
        df["处理人"] = df["催费员"]
        df = df[["序号",	"*工单类型", "工单名称", "工单时限",	"时限单位",	"自然日/工作日",	"*工单内容",	"工单对象地址",	"工单对象类型",	"业务编号",	"处理人isc账号","处理人"]].copy()
        df.to_excel("待建工单.xlsx", index=False)
        report(step, "已生成批量工单导入excel",flow = flow)


def main(**kwargs):
    # report_all(['浏览器后台运行中', '登录营销2.0', '切换岗位-站所-班组长-站所长', '打开费控欠费客户情况查询','配置查询条件', '读取费控用户欠费明细', '数据清洗', '打印欠费用户', '结束'])
    report_all({"导出数据":['浏览器后台运行中', '登录系统', '切换岗位', '打开费控欠费客户情况查询','配置查询条件', '读取费控用户欠费明细','读取催费员明细'],
                "数据清洗":['数据清洗', '打印欠费用户', '结束']
    })

    Base.run(**kwargs)
    # report_all([])
    

def cjgd(**kwargs):
    report_all(['读取费控用户欠费明细数据完成', '已生成批量工单导入excel'])
    Base.cjgd(**kwargs)
    # report_all([])


