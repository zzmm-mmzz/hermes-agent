"""
EIP Cookie 获取中转服务
本地启动 HTTP 服务，用户在已登录的浏览器中访问页面，通过表单提交 Cookie
"""
import json
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

EIP_HOST = "http://eip.hn.sgcc.com.cn"
HOST = "0.0.0.0"
PORT = 8899

PAGE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>EIP 数据助手 - Cookie 中转</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, "Microsoft YaHei", sans-serif; background: #f0f2f5; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
.card { background: #fff; border-radius: 12px; padding: 32px; width: 600px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
h2 { color: #1a1a2e; margin-bottom: 20px; border-bottom: 2px solid #1890ff; padding-bottom: 10px; }
.step { background: #f6f8fa; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.step h3 { color: #1890ff; font-size: 14px; margin-bottom: 8px; }
.step p { color: #555; font-size: 13px; line-height: 1.8; }
.code { background: #1e1e2e; color: #cdd6f4; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 12px; margin: 8px 0; word-break: break-all; }
.btn { background: #1890ff; color: #fff; border: none; padding: 10px 24px; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn:hover { background: #40a9ff; }
.btn:disabled { background: #ccc; cursor: not-allowed; }
textarea { width: 100%; height: 100px; border: 1px solid #d9d9d9; border-radius: 6px; padding: 10px; font-family: monospace; font-size: 12px; margin: 10px 0; }
.status { margin-top: 12px; padding: 10px; border-radius: 6px; display: none; }
.status.success { background: #f6ffed; border: 1px solid #b7eb8f; color: #52c41a; display: block; }
.status.error { background: #fff2f0; border: 1px solid #ffccc7; color: #ff4d4f; display: block; }
.step-num { display: inline-flex; width: 24px; height: 24px; background: #1890ff; color: #fff; border-radius: 50%; align-items: center; justify-content: center; font-size: 13px; margin-right: 8px; }
</style>
</head>
<body>
<div class="card">
<h2>EIP 门户数据助手</h2>

<div class="step">
  <h3><span class="step-num">1</span> 获取 Cookie</h3>
  <p>在已登录 EIP 门户的浏览器中，按 <strong>F12</strong> 打开开发者工具，切换到 <strong>Console</strong>（控制台），粘贴以下代码后回车：</p>
  <div class="code" id="cookieCode">copy(document.cookie); console.log('Cookie 已复制到剪贴板！');</div>
  <button class="btn" onclick="copyCode()">复制代码</button>
</div>

<div class="step">
  <h3><span class="step-num">2</span> 粘贴 Cookie</h3>
  <p>将第一步复制的 Cookie 粘贴到下方输入框中：</p>
  <textarea id="cookieInput" placeholder="在此粘贴 Cookie..."></textarea>
  <button class="btn" id="submitBtn" onclick="submitCookie()">提交 Cookie 获取数据</button>
</div>

<div id="status" class="status"></div>

<div class="step" id="resultArea" style="display:none;">
  <h3>数据结果</h3>
  <div id="dataContent"></div>
</div>
</div>

<script>
function copyCode() {
  navigator.clipboard.writeText(document.getElementById('cookieCode').textContent);
  alert('已复制到剪贴板');
}

async function submitCookie() {
  const cookie = document.getElementById('cookieInput').value.trim();
  if (!cookie) {
    showStatus('请先粘贴 Cookie', 'error');
    return;
  }

  const btn = document.getElementById('submitBtn');
  btn.disabled = true;
  btn.textContent = '请求中...';
  showStatus('正在获取邮件列表和待办列表...', '');

  try {
    const resp = await fetch('/fetch-data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cookie: cookie })
    });
    const result = await resp.json();
    
    if (result.success) {
      showStatus('数据获取成功！', 'success');
      document.getElementById('resultArea').style.display = 'block';
      
      let html = '';
      
      if (result.mail && result.mail.length > 0) {
        html += '<h4 style="margin:12px 0 8px;color:#1890ff;">邮件列表 (' + result.mail.length + ' 条)</h4>';
        html += '<table border="1" cellpadding="6" cellspacing="0" style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:16px;">';
        html += '<tr style="background:#fafafa;"><th>主题</th><th>发件人</th><th>时间</th></tr>';
        result.mail.forEach(function(m) {
          html += '<tr><td>' + (m.subject || m.title || '-') + '</td><td>' + (m.sender || m.from || '-') + '</td><td>' + (m.time || m.date || '-') + '</td></tr>';
        });
        html += '</table>';
      }
      
      if (result.todo && result.todo.length > 0) {
        html += '<h4 style="margin:12px 0 8px;color:#1890ff;">待办列表 (' + result.todo.length + ' 条)</h4>';
        html += '<table border="1" cellpadding="6" cellspacing="0" style="width:100%;border-collapse:collapse;font-size:12px;">';
        html += '<tr style="background:#fafafa;"><th>任务</th><th>应用</th><th>类型</th><th>时间</th></tr>';
        result.todo.forEach(function(t) {
          html += '<tr><td>' + (t.title || t.taskName || '-') + '</td><td>' + (t.appName || '-') + '</td><td>' + (t.taskTypeName || '-') + '</td><td>' + (t.createTime || t.time || '-') + '</td></tr>';
        });
        html += '</table>';
      }
      
      if (!html) {
        html = '<p>未获取到数据，请检查 Cookie 是否有效。</p>';
      }
      
      document.getElementById('dataContent').innerHTML = html;
      
    } else {
      showStatus('请求失败: ' + (result.error || '未知错误'), 'error');
    }
  } catch (e) {
    showStatus('请求出错: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '提交 Cookie 获取数据';
  }
}

function showStatus(msg, type) {
  const el = document.getElementById('status');
  el.textContent = msg;
  el.className = 'status' + (type ? ' ' + type : '');
}
</script>
</body>
</html>"""


class EIPProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(PAGE_HTML.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_POST(self):
        if self.path == "/fetch-data":
            content_len = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_len).decode("utf-8"))
            cookie = body.get("cookie", "")

            if not cookie:
                self._json_response({"success": False, "error": "Cookie is empty"})
                return

            result = {"success": True, "mail": [], "todo": []}

            # 尝试多个可能的待办和邮件接口
            api_list = {
                "todo": [
                    "/portal/portal_ext/rest/task/listHis?pageSize=10",
                    "/portal/portal_ext/rest/task/list?pageSize=10",
                    "/portal/portal_ext/rest/todo/list?pageSize=10",
                    "/portal/portal_ext/rest/task/pendingList?pageSize=10",
                ],
                "mail": [
                    "/portal/portal_ext/rest/mail/list?pageSize=10",
                    "/portal/portal_ext/rest/email/list?pageSize=10",
                    "/portal/portal_ext/rest/message/list?pageSize=10",
                    "/portal/portal_ext/rest/notice/list?pageSize=10",
                ],
            }

            for category, urls in api_list.items():
                for path in urls:
                    api_url = f"http://eip.hn.sgcc.com.cn{path}"
                    try:
                        curl_cmd = [
                            "curl", "-s", "-L", api_url,
                            "-H", f"Cookie: {cookie}",
                            "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            "-H", "Accept: application/json, text/plain, */*",
                            "-H", "Referer: http://eip.hn.sgcc.com.cn/portal/",
                            "--connect-timeout", "8",
                            "--max-time", "15",
                        ]
                        resp = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=20)
                        output = resp.stdout.strip()

                        if not output:
                            continue

                        # Try to parse as JSON
                        try:
                            data = json.loads(output)
                            # Extract list
                            items = None
                            if isinstance(data, dict):
                                if "data" in data and isinstance(data["data"], dict):
                                    items = data["data"].get("list") or data["data"].get("rows") or data["data"].get("records")
                                items = items or data.get("list") or data.get("rows") or data.get("records") or data.get("data")
                            if items and len(items) > 0:
                                result[category] = items
                                break  # Found a working API
                        except json.JSONDecodeError:
                            continue
                    except Exception:
                        continue

            self._json_response(result)
        else:
            self._json_response({"success": False, "error": "Not Found"}, 404)

    def _json_response(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Reduce noise


def main():
    server = HTTPServer((HOST, PORT), EIPProxyHandler)
    print(f"")
    print(f"  EIP Cookie 中转服务已启动")
    print(f"  ─────────────────────────────")
    print(f"  请在浏览器中访问:")
    print(f"  http://127.0.0.1:{PORT}")
    print(f"")
    print(f"  步骤: 在已登录EIP的浏览器中打开F12")
    print(f"  Console -> 粘贴并执行: copy(document.cookie)")
    print(f"  将Cookie粘贴到页面输入框即可获取数据")
    print(f"")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")


if __name__ == "__main__":
    main()
