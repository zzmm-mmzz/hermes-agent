# -*- coding:utf-8 -*-

import os
import re
import time
import functools
import ctypes
import win32api
import win32con
from abc import ABC, abstractmethod
import requests
from datetime import datetime, timedelta
import json
import pandas as pd
from lxml import etree
import csv
from io import StringIO
import argparse

from contextlib import ExitStack

# Playwright 同步 API
from playwright.sync_api import Playwright, sync_playwright, expect

from dotenv import load_dotenv

load_dotenv('.env', override=True)

# IP 地址常量
ISC_SSO_URL = os.getenv('ISC_SSO_URL')
YX20_SYS_URL = os.getenv('YX20_SYS_URL')
EMSS_COC_URL = os.getenv('EMSS_COC_URL')

def active() -> None:
    """
    Win + D 组合键：返回桌面
    """
    win32api.keybd_event(91, 0, 0, 0)          # Win 键按下
    time.sleep(0.1)
    win32api.keybd_event(68, 0, 0, 0)          # D 键按下
    time.sleep(0.1)
    win32api.keybd_event(68, 0, win32con.KEYEVENTF_KEYUP, 0)  # D 键抬起
    win32api.keybd_event(91, 0, win32con.KEYEVENTF_KEYUP, 0)  # Win 键抬起


class Browser(ABC):
    """封装 Playwright Browser 的同步辅助类"""

    def __init__(self, browser, debug=False, storage_state=None, tp=None):
        """
        :param browser: Playwright 的 Browser 对象
        """
        self.browser = browser
        self.page = None
        self.context = None
        self.debug = debug
        self.storage_state = storage_state
        if not tp:
            self.new_context()
        else:
            self.new_context2()

    def set_context(self, context, page):
        """从外部设置 context 和 page（CDP 模式复用已有）"""
        self.context = context
        self.page = page

    def new_context(self):
        """
        创建新的浏览器上下文和页面
        """
        width = win32api.GetSystemMetrics(0)
        height = win32api.GetSystemMetrics(1)
        if width <= 1920 or height <= 1080:
            width, height = 1920, 1080
        self.context = self.browser.new_context(locale='en-US', no_viewport=True,viewport = {"width":width,"height":height})
        # self.context = self.browser.new_context(locale='en-US', no_viewport=True,viewport = {"width":1920,"height":1080})
        # self.context = self.browser.new_context(locale='en-US', no_viewport=True)
        self.page = self.context.new_page()
        # self.page = self.browser.new_page()
        # self.page.set_viewport_size({"width": 1920, "height": 1080})
        return self.page, self.context

    def new_context2(self):
        """
        复用 CDP 已有浏览器 context/page，不创建新窗口
        """
        contexts = self.browser.contexts
        if contexts:
            context = contexts[0]
            self.context = context
            pages = context.pages
            self.page = pages[0] if pages else context.new_page()
            # 新 page 可能触发安全检测，用第一页
            if len(pages) > 1:
                self.page = pages[0]
        else:
            context = self.browser.new_context(ignore_https_errors=True)
            self.page = context.new_page()
            self.context = context
        # 清空当前页导航到 about:blank
        # self.page.goto("about:blank", wait_until="commit")
        # self.page.set_viewport_size({"width": 1920, "height": 1080})
        return self.page, self.browser

    def click(self, selector: str, **kwargs):
        """
        点击页面元素
        """
        self.page.bring_to_front()
        locator = self.locator_first(selector)
        self.highlight(locator)
        locator.click(**kwargs)
        # self.wait_for_timeout(500)

    def dblclick(self, selector: str, **kwargs):
        """
        双击
        """
        self.page.bring_to_front()
        locator = self.locator_first(selector)
        self.highlight(locator)
        locator.dblclick(**kwargs)
        # self.wait_for_timeout(500)

    def hover(self, selector: str, **kwargs):
        """
        hover
        """
        self.page.bring_to_front()
        locator = self.locator_first(selector)
        self.highlight(locator)
        locator.hover(**kwargs)
        # self.wait_for_timeout(500)

    def goto(self, url: str, **kwargs):
        """
        跳转到指定 URL（CDP 模式：忽略 HTTPS 错误，不等待网络空闲）
        """
        self.page.bring_to_front()
        kwargs.setdefault('timeout', 60000)
        kwargs.setdefault('wait_until', 'commit')
        url = url.replace('https://', 'http://')
        self.page.goto(url, **kwargs)
        # self.wait_for_timeout(500)

    def locator(self, selector: str, **kwargs):
        """
        返回 locator 对象
        """
        # self.wait_for_timeout(500)
        locator = self.page.locator(selector, **kwargs)
        # self.wait_for_timeout(500)
        self.highlight(locator)
        return locator

    def locator_first(self, selector: str, **kwargs):
        """
        返回匹配的第一个 locator
        """
        locators = self.locator(selector, **kwargs)
        if not locators.count():
            raise AssertionError("元素未找到")
        return locators.first

    def input(self, selector: str, text: str):
        """
        在输入框中填入文本
        """
        self.page.bring_to_front()
        locator = self.locator(selector)
        locator.fill(text)

    def read(self, selector: str) -> str | None:
        """
        读取单个元素的文本内容
        """
        self.page.bring_to_front()
        locator = self.locator(selector)
        return locator.text_content(selector)

    def readall(self, selector: str) -> list[str]:
        """
        读取一组元素的文本内容
        """
        self.page.bring_to_front()
        # self.wait_for_timeout(500)
        locator = self.locator(selector)
        return locator.all_text_contents()

    def get_by_text(self, text: str, **kwargs):
        """
        根据文本获取元素
        """
        # self.wait_for_timeout(500)
        self.page.bring_to_front()
        locator = self.page.get_by_text(text, **kwargs)
        # self.wait_for_timeout(500)
        self.highlight(locator)
        return locator

    def get_by_role(self, role: str, **kwargs):
        """
        根据 role 获取元素
        """
        # self.wait_for_timeout(500)
        self.page.bring_to_front()
        locator = self.page.get_by_role(role, **kwargs)
        # self.wait_for_timeout(500)
        self.highlight(locator)
        return locator

    def highlight(self, locator):
        """
        """
        if self.debug:
            try:
                locator.highlight()
            except Exception as e:
                pass

    def expect_popup(self, **kwargs):
        # self.wait_for_timeout(1000)
        return self.page.expect_popup(**kwargs)

    def wait_user(self, el, state='hidden', timeout=30*1000):
        """
        等待用户处理
        """
        # 1.元素加载
        el.wait_for()
        el.hover()

        step = 30 * 1000
        for i in range(0, timeout, step):
            try:
                el.wait_for(state=state, timeout=step)
                return
            except Exception as e:
                print(e)
                pass
        raise Exception(f'{el}用户一直未处理，等待超时')

    def wait_for_timeout(self,*args,**kwargs):
        """
        wait_for_timeout
        """
        return self.page.wait_for_timeout(*args,**kwargs)

    def login(self, username, password):
        """
        isc登录
        """
        url = f'{ISC_SSO_URL}/isc_sso/login'
        print(url)
        self.page.goto(url)
        self.get_by_role("textbox", name="请输入您的账号").click()
        self.get_by_role("textbox", name="请输入您的账号").click()
        self.get_by_role("textbox", name="请输入您的账号").fill(username)
        self.get_by_role("textbox", name="请输入您的密码").click()
        self.get_by_role("textbox", name="请输入您的密码").fill(password)
        self.get_by_role("button", name="立即登录").click()
        # self.wait_for_timeout(2000)
        result = self.locator(r'main[role=main] div.row div.alert-success').text_content()
        print(self.page.url)
        self.context.storage_state(path="state.json")
        return '登录成功' in result


class YX20(Browser):
    """营销2.0系统 封装类：浏览器启动 + 登录 + 岗位切换 + 菜单导航"""

    def login_yx20(self):
        """登录营销2.0系统（#loginFrame 模式）"""
        try:
            self.goto(f"{YX20_SYS_URL}/cmn/login")

            self.locator('body input#user_tag').fill(USERNAME3)
            # self.wait_for_timeout(1000)
            self.locator('body input#user_pd').fill(PASSWORD3)
            # self.wait_for_timeout(1000)
            self.locator('body button#submi').click()
            # 确保登录成功
            self.wait_for_timeout(2000)

            # 检查登录后的 URL 是否包含 login，包含则表示登录失败
            current_url = self.page.url
            if 'login' in current_url.lower():
                print(f"登录失败，当前 URL 仍包含 login: {current_url}")
                return False

            return True
        except Exception as e:
            print(f"登录营销2.0异常: {e}")
            return False

    def login_isc_sso(self, service_url=None):
        """登录营销2.0系统（ISC SSO 模式）"""
        if service_url:
            url = f'{ISC_SSO_URL}/isc_sso/login?service={service_url}'
        else:
            url = f'{ISC_SSO_URL}/isc_sso/login'
        self.goto(url)
        # report(1, "打开浏览器完成")
        self.get_by_role("textbox", name="请输入您的账号").fill(USERNAME)
        self.get_by_role("textbox", name="请输入您的密码").fill(PASSWORD)
        self.get_by_role("button", name="立即登录").click()
        # 确保登录成功
        self.wait_for_timeout(1000)
        # report(2, "登录营销2.0完成")

    def switch_role(self, role_text):
        """切换岗位"""
        # self.get_by_text(USERNAME).click()
        self.locator('div.userName').click()
        # self.wait_for_timeout(100)
        self.get_by_text("切换岗位").click()
        # self.wait_for_timeout(100)
        self.get_by_text(role_text).click()
        # self.wait_for_timeout(100)
        # report(3, f"切换岗位-{role_text}成功")

    def navigate_menu(self, search_app, menu_path):
        """
        菜单导航
        :param search_app: 搜索的应用名称
        :param menu_path: 菜单点击路径列表
        """
        self.get_by_role("textbox", name="请输入内容").click()
        self.get_by_role("textbox", name="请输入内容").fill(search_app)
        for menu_item in menu_path:
            self.locator(".el-submenu__title").get_by_text(menu_item, exact=True).click()
            # self.wait_for_timeout(500)

    def navigate_menu2(self, search_app, menu_items):
        """
        菜单导航（适用于部分使用 .menu-item-title 的情况）
        """
        self.get_by_role("textbox", name="请输入内容").click()
        self.get_by_role("textbox", name="请输入内容").fill(search_app)
        for item in menu_items:
            if isinstance(item, dict) and 'menu_item_title' in item:
                self.locator(".menu-item-title").get_by_text(item['menu_item_title']).click()
            else:
                self.locator(".el-submenu__title").get_by_text(item, exact=True).click()
            # self.wait_for_timeout(100)


# 格式化输出表格
def desc_data(df):
    """
    打印数据
    """
    columns = list(df.columns)
    records = list(df.values)
    print("| " + " | ".join(columns) + " |")
    print("| " + " | ".join(map(lambda x: ":-:", columns)) + " |")

    for record in records:
        print("| " + " | ".join(map(lambda x: str(x), record)) + " |")


def new_df(*columns):
    """
    新建空白 DataFrame，指定一个或多个列名
    :param columns: 列名（可传多个字符串参数）
    :return: 空的 pd.DataFrame
    """
    return pd.DataFrame({col: [] for col in columns})

# ==========================================
# 客户端进度推送配置（与 client.py 一致）
# ==========================================

CLIENT_BASE_URL = "http://127.0.0.1:6789"
SCRIPT_PROGRESS_URL = f"{CLIENT_BASE_URL}/capi/script-progress"


def _report_to_client(data):
    """通过 HTTP POST 将进度数据上报到 client.py"""
    try:
        resp = requests.post(SCRIPT_PROGRESS_URL, json=data, timeout=3)
        if resp.status_code != 200:
            print(f"[上报失败] HTTP {resp.status_code}", flush=True)
    except Exception as e:
        # 如果 client.py 未启动，静默忽略，不影响脚本本身执行
        pass

def step_wrapper(func):
    """步骤装饰器：出现异常立即中断流程并上报，不继续执行后续步骤。

    用法:
        class Base():
            @step_wrapper
            def _login(self, page, step=2, flow=None):
                ...
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            step = kwargs.get("step", "?")
            flow = kwargs.get("flow")
            msg = f"步骤{step}-{func.__name__} 执行失败: {e}"
            print(msg)
            report(step, msg, flow=flow)
            raise RuntimeError(msg) from e
    return wrapper

def step_wrapper_quiet(func):
    """步骤装饰器：捕捉到异常时仅 report 上报，不中断流程，继续执行后续步骤。

    用法:
        class Base():
            @step_wrapper_quiet
            def _xxx(self, page, step=2, flow=None):
                ...
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            step = kwargs.get("step", "?")
            flow = kwargs.get("flow")
            msg = f"步骤{step}-{func.__name__} 执行失败(已跳过): {e}"
            print(msg)
            report(step, msg, flow=flow)
    return wrapper

def report(step, action,flow=None):

    data = {"type": "progress", "step": step, "action": action, "flow": flow}
    # print(json.dumps(data, ensure_ascii=False), flush=True)
    _report_to_client(data)

def report_all(data):
    if isinstance(data,list):
        steps = data
        steps_data = {"type": "total_steps", "total": len(steps), "steps": steps}
    elif isinstance(data,dict):
        result = dict()
        steps = []
        for k,v in data.items():
            if v and isinstance(v,list):
                result[k] = {"steps":v,"count":len(v)}
                steps = steps + v
        steps_data = {"type": "total_steps", "total": len(steps), "steps": steps,"flows" : result}
    else:
        steps_data = {"type": "total_steps", "total": 0, "steps": []}
    # print(steps_data)
    _report_to_client(steps_data)

def remote_log(op_type,op_dtl,**kwargs):
    """ 远程日志上报 
        params:
            op_type: 操作类型，SELECT/CREATE/EDIT/APPROVE/FINISH/WITHDRAW/DELETE/BATCH_CREATE/EXPORT
            workst_no: 工单编号
            workst_tp: 工单类型
            batch_id: 批次编号
            op_dtl: 操作内容
            operator: AI接管桌面登录账号
            op_ip: 脚本执行ip
    """

    tm = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    batch_id = kwargs.get("batch_id")
    if batch_id:
        batch_id = f'{batch_id}'

    data = {
        "events": [
                {
                "opTime": tm,
                "opType": op_type,
                "workorderNo": kwargs.get("workst_no"),
                "workorderType": kwargs.get("workst_tp"),
                "operator": kwargs.get('operator'),
                "opUser": USERNAME3,
                "opIp": kwargs.get('op_ip'),
                "source": kwargs.get("source","AI_DESKTOP"),
                "batchId": batch_id,
                "opDetail": op_dtl
                }
            ]
    }
    try:
        resp = requests.post('http://127.0.0.1:6789/forward/op', json=data, timeout=3)
        if resp.status_code != 200:
            print(f"[上报失败] HTTP {resp.status_code}", flush=True)
    except Exception as e:
        # 如果 client.py 未启动，静默忽略，不影响脚本本身执行
        pass


"""
SM2 解密脚本 —— 使用 gmssl 库
对 C1C2C3 模式的 SM2 密文进行解密
"""
import base64
import requests
from gmssl.sm2 import CryptSM2
from gmssl.sm3 import sm3_hash, sm3_kdf

# SM2 私钥（从 .env 读取，开发阶段也支持硬编码兜底）
DEFAULT_PRIVATE_KEY = os.getenv('SM2_PRIVATE_KEY', '28e4981f7bfb040f6bd51367c4b803d3f029cc247200b7150f4df66585fad711')


def sm2_decrypt(cipher_base64: str | None) -> bytes:
    """
    对 Base64 编码的 SM2 密文进行解密，返回明文字节。

    参数:
        cipher_base64: Base64 编码的密文字符串，可能为 None 或空串。

    返回:
        bytes 类型明文。若解密失败返回 b''。

    异常:
        正常情况下不抛出异常，所有异常内部捕获并记录日志。
        调用方通过返回值判断：返回空 bytes 表示解密失败。
    """
    # 1. 空/None 校验
    if not cipher_base64:
        print("WARNING: sm2_decrypt 收到空密文（None 或空字符串），返回空字节")
        return b''

    try:
        # 2. Base64 解码
        cipher_bytes = base64.b64decode(cipher_base64)
    except Exception as e:
        print(f"Base64 解码失败: {e}")
        return b''

    try:
        data_hex = cipher_bytes.hex()

        # 首字节 04 为未压缩标记，去掉
        if len(data_hex) > 2 and data_hex[:2] == '04':
            data_hex = data_hex[2:]

        # 长度校验：至少需要 C1(128) + C3(64) = 192 hex 字符
        if len(data_hex) < 192:
            print(f"密文数据长度不足（{len(data_hex)} < 192 hex），可能数据损坏")
            return b''

        # C1=64字节(128hex), C3=32字节(64hex), C2=剩余
        C1 = data_hex[:128]
        C2 = data_hex[128:-64]
        C3 = data_hex[-64:]

        if not C2:
            print("密文数据中 C2 部分为空")
            return b''

        # 计算共享点 xy = private_key * C1
        cryptor = CryptSM2(private_key='', public_key='')
        xy = cryptor._kg(int(DEFAULT_PRIVATE_KEY, 16), C1)

        x2 = xy[:64]
        y2 = xy[64:128]

        # KDF 派生密钥
        cl = len(C2)
        t = sm3_kdf(xy.encode('utf8'), cl // 2)

        # XOR 解密得明文 M
        M = f'{int(C2, 16) ^ int(t, 16):0{cl}x}'

        # 验证 C3：sm3_hash 接受 int 列表
        u = sm3_hash(list(bytes.fromhex(f'{x2}{M}{y2}')))
        if u != C3:
            print("C3 校验失败，数据可能被篡改或私钥不正确")
            return b''

        return bytes.fromhex(M)

    except Exception as e:
        print(f"SM2 解密过程发生异常: {e}")
        return b''

# 获取登录相关信息
def get_login_info(ipport):
    """
    从本地 API 获取用户登录信息并解密密码。

    返回:
        (username, password, msg) 元组。
        username: 用户名字符串，失败时为 None。
        password: 解密后的密码字节，失败时为 None。
        msg: 错误信息（成功时为空字符串）。

    异常:
        网络不通或数据异常时抛出 ConnectionError / RuntimeError 等具体异常。
    """
    url = "http://127.0.0.1:6789/capi/get_credentials"

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except requests.ConnectionError:
        raise ConnectionError(f"无法连接到客户端服务，请检查 http://127.0.0.1:6789 的连通性（client.py 是否已启动？）")
    except requests.RequestException as e:
        raise RuntimeError(f"请求凭证 API 失败: {e}")

    try:
        result = resp.json()
    except ValueError as e:
        raise RuntimeError(f"凭证 API 返回非合法 JSON: {e}")

    code = result.get('code', '-1')
    msg = result.get('msg', '')

    if code == '-1':
        raise RuntimeError(msg or "凭证 API 返回错误码 -1，登录凭证获取失败")

    data = result.get('data', {})
    records = data.get('records', [])
    if not records:
        raise RuntimeError("凭证 API 返回的 records 为空，请检查是否有账号记录")
    records = [x for x in records if x.get('address') == ipport]
    if not records:
        raise RuntimeError(f"未找到{ipport}记录，请检查是否有账号记录")

    first_record = records[0]
    username = first_record.get('username')
    if not username:
        raise RuntimeError("凭证 API 返回的 username 为空")

    password_encoded = first_record.get('password')
    if not password_encoded:
        raise RuntimeError("凭证 API 返回的 password 为空")

    password = sm2_decrypt(password_encoded)
    if not password:
        # SM2 解密失败时，尝试将 password 作为明文使用
        print("SM2 解密返回空，尝试将 password 作为明文使用")
        password = password_encoded.encode()

    return username, password.decode(), msg



USERNAME,PASSWORD,_ = get_login_info(ipport = 'hnyx2.hn.sgcc.com.cn:80')
# USERNAME2,PASSWORD2,_ = get_login_info(ipport = '配网微应用cs')
USERNAME3,PASSWORD3,_ = get_login_info(ipport = '配网微应用')

# 获取静默模式
# mode = 0 普通模式
# mode = 1 静默模式

def get_mode():
    """
    是否静默模式
    returns:
        mode 是否静默模式 0 普通模式 1 静默模式
    """
    url = "http://127.0.0.1:6789/capi/get-flag"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        result = resp.json()
    except Exception as e:
        raise ConnectionError(f"无法获取到是否静默模式，请检查 http://127.0.0.1:6789/capi/get-flag 的连通性（client客户端 是否已启动？）") from e
    data = result.get('data',{})
    if data:
        flag = data.get('value',False)
    else:
        flag = False
    return '1' if flag else '0'