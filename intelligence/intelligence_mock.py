"""Simple HTTP mock server for intelligence center API.
Runs on port 10010 inside the container alongside the Gateway."""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

MOCK_DATA = [
    {"id": "1", "title": "湖南电网迎峰度夏保供电工作有序推进",
     "summary": "预计今夏全省最大负荷将达到4800万千瓦，同比增长8.3%。",
     "content": "国网湖南电力召开2026年迎峰度夏保供电工作会议。预计今夏全省最大负荷将达到4800万千瓦，同比增长8.3%。",
     "category": "电力要闻", "status": "已发布", "publishTime": "2026-06-15 10:30:00",
     "author": "国网湖南电力", "source": "内部情报", "viewCount": 856},
    {"id": "2", "title": "新型电力系统建设取得阶段性成果",
     "summary": "湖南新型电力系统建设示范工程通过专家组验收，为全国提供了可复制的湖南经验。",
     "content": "湖南新型电力系统建设示范工程通过专家组验收，涵盖源网荷储一体化、分布式光伏智能调控等关键技术。",
     "category": "行业动态", "status": "已发布", "publishTime": "2026-06-14 14:00:00",
     "author": "国网湖南电力", "source": "内部情报", "viewCount": 723},
    {"id": "3", "title": "配电网数字化转型三年行动计划发布",
     "summary": "计划到2028年底全面建成数字化配电网，供电可靠率提升至99.99%。",
     "content": "国网湖南电力正式印发《配电网数字化转型三年行动计划（2026-2028）》。",
     "category": "政策文件", "status": "已发布", "publishTime": "2026-06-13 09:00:00",
     "author": "国网湖南电力", "source": "内部情报", "viewCount": 634},
    {"id": "4", "title": "湖南电力市场交易电量突破500亿千瓦时",
     "summary": "累计交易电量突破500亿千瓦时，参与交易的市场主体超过8000家。",
     "content": "截至2026年5月底，湖南电力市场累计交易电量突破500亿千瓦时。",
     "category": "电力市场", "status": "已发布", "publishTime": "2026-06-12 16:00:00",
     "author": "国网湖南电力", "source": "内部情报", "viewCount": 512},
    {"id": "5", "title": "AI输电线路智能巡检系统全面上线",
     "summary": "基于深度学习的缺陷识别准确率达到98.5%，可识别16类典型缺陷。",
     "content": "湖南电网输电线路智能巡检系统完成全省覆盖。",
     "category": "科技创新", "status": "已发布", "publishTime": "2026-06-11 11:00:00",
     "author": "国网湖南电力", "source": "内部情报", "viewCount": 945},
]

CATEGORIES = [
    {"name": "电力要闻", "count": 2},
    {"name": "行业动态", "count": 2},
    {"name": "政策文件", "count": 1},
    {"name": "电力市场", "count": 1},
    {"name": "科技创新", "count": 1},
]

class MockHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/api/intelligence/list":
            page = int(params.get("page", ["1"])[0])
            limit = int(params.get("limit", ["10"])[0])
            total = len(MOCK_DATA)
            start = (page - 1) * limit
            end = min(start + limit, total)
            items = []
            for item in MOCK_DATA[start:end]:
                slim = dict(item)
                # list 接口不带完整 content
                slim.pop("content", None)
                slim["hasDetail"] = True
                items.append(slim)
            self._ok({"data": items, "total": total, "page": page, "limit": limit})

        elif path == "/api/intelligence/detail":
            item_id = params.get("id", [""])[0]
            for item in MOCK_DATA:
                if item["id"] == item_id:
                    self._ok({"data": item})
                    return
            self._ok({"error": "not found"}, 404)

        elif path == "/api/intelligence/categories":
            self._ok({"data": CATEGORIES})

        elif path == "/api/auth/token":
            self._ok({"access_token": "mock-token-12345", "expires_in": 3600})

        else:
            self._ok({"error": "not found"}, 404)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode() if content_length else "{}"
        req = json.loads(body) if body else {}

        if self.path == "/api/intelligence/list":
            page = int(req.get("page", 1))
            limit = int(req.get("limit", 10))
            total = len(MOCK_DATA)
            start = (page - 1) * limit
            end = min(start + limit, total)
            items = []
            for item in MOCK_DATA[start:end]:
                slim = dict(item)
                slim.pop("content", None)
                slim["hasDetail"] = True
                items.append(slim)
            self._ok({"data": items, "total": total, "page": page, "limit": limit})

        elif self.path == "/api/auth/token":
            self._ok({"access_token": "mock-token-12345", "expires_in": 3600})
        else:
            self._ok({"error": "not found"}, 404)

    def _ok(self, data, status=200):
        body = json.dumps({"success": True, "code": 200, **data}, ensure_ascii=False)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body.encode())))
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, fmt, *args):
        pass  # 安静，别刷日志


def start_mock_server():
    import threading
    server = HTTPServer(("0.0.0.0", 10010), MockHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"[intelligence-mock] Mock server running on http://0.0.0.0:10010")


if __name__ == "__main__":
    start_mock_server()
    import time
    while True:
        time.sleep(3600)
