"""indicators - 指标管理 & 执行模块

主网关挂载方式（在 api_server.py connect() 中）:
    from indicators.api import make_app as _make_indicators_app, init as _init_indicators
    _init_indicators()
    _indicators_app = _make_indicators_app()
    # 逐路由复制到 self._app
"""
