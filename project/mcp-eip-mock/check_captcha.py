"""检查验证码配置"""
import requests
import re

SSO_BASE = "http://tyqxiscsso.hn.sgcc.com.cn:38080"
EIP_PORTAL = "http://eip.hn.sgcc.com.cn/portal"

session = requests.Session()
resp = session.get(f"{EIP_PORTAL}/", allow_redirects=False, timeout=15)
login_url = resp.headers.get("Location", "")

resp = session.get(login_url, timeout=15)
html = resp.text

# 检查验证码相关配置
for pattern in ['captchaEmbed', 'captchaPopup', 'isPreLoginCheck', 'captchaPattern', 'slider-popup']:
    for m in re.finditer(r'.{0,30}' + pattern + r'.{0,100}', html):
        print(f"{pattern}: ...{m.group()}...")
        print()
