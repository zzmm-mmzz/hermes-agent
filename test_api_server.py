"""
Combined API server: Hermes Agent management endpoints + SkillHub skill endpoints
on a single port (8643).

Usage:
    cd "G:/hermes agent/hermes-agent"
    python test_api_server.py

Then test:
    curl http://127.0.0.1:8643/api/security/mode
    curl http://127.0.0.1:8643/api/skills
"""

import asyncio
import sys
import os
import socket as _socket

# Ensure the project root is on sys.path so imports resolve correctly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aiohttp import web

from gateway.platforms.api_server import APIServerAdapter
from gateway.config import Platform, PlatformConfig

# Import hub API routes builder
from hub_api_server import make_app as make_hub_app

HOST = "127.0.0.1"
PORT = 8643


async def main():
    # ------------------------------------------------------------------
    # 1. Resolve middlewares (same as APIServerAdapter.connect())
    # ------------------------------------------------------------------
    try:
        from gateway.platforms.api_server import (
            cors_middleware,
            body_limit_middleware,
            security_headers_middleware,
        )
    except ImportError:
        cors_middleware = body_limit_middleware = security_headers_middleware = None

    mws = [mw for mw in (cors_middleware, body_limit_middleware, security_headers_middleware) if mw is not None]
    app = web.Application(middlewares=mws)

    # ------------------------------------------------------------------
    # 2. Create APIServerAdapter and register its routes on our app
    # ------------------------------------------------------------------
    config = PlatformConfig(
        enabled=True,
        extra={"host": HOST, "port": PORT},
    )
    server = APIServerAdapter(config)
    app["api_server_adapter"] = server

    # Register management routes (same set as APIServerAdapter.connect())
    app.router.add_get("/health", server._handle_health)
    app.router.add_get("/health/detailed", server._handle_health_detailed)
    app.router.add_get("/v1/health", server._handle_health)
    app.router.add_get("/v1/models", server._handle_models)
    app.router.add_get("/v1/capabilities", server._handle_capabilities)
    app.router.add_post("/v1/chat/completions", server._handle_chat_completions)
    app.router.add_post("/v1/responses", server._handle_responses)
    app.router.add_get("/v1/responses/{response_id}", server._handle_get_response)
    app.router.add_delete("/v1/responses/{response_id}", server._handle_delete_response)
    app.router.add_get("/api/jobs", server._handle_list_jobs)
    app.router.add_post("/api/jobs", server._handle_create_job)
    app.router.add_get("/api/jobs/{job_id}", server._handle_get_job)
    app.router.add_patch("/api/jobs/{job_id}", server._handle_update_job)
    app.router.add_delete("/api/jobs/{job_id}", server._handle_delete_job)
    app.router.add_post("/api/jobs/{job_id}/pause", server._handle_pause_job)
    app.router.add_post("/api/jobs/{job_id}/resume", server._handle_resume_job)
    app.router.add_post("/api/jobs/{job_id}/run", server._handle_run_job)
    app.router.add_get("/api/security/mode", server._handle_get_security_mode)
    app.router.add_post("/api/security/mode", server._handle_set_security_mode)
    app.router.add_get("/api/sandbox", server._handle_get_sandbox)
    app.router.add_post("/api/sandbox", server._handle_set_sandbox)
    app.router.add_get("/api/workdir", server._handle_get_workdir)
    app.router.add_post("/api/workdir", server._handle_set_workdir)
    app.router.add_get("/api/audit/log", server._handle_get_audit_log)
    app.router.add_delete("/api/audit/log", server._handle_clear_audit_log)
    app.router.add_post("/v1/runs", server._handle_runs)
    app.router.add_get("/v1/runs/{run_id}", server._handle_get_run)
    app.router.add_get("/v1/runs/{run_id}/events", server._handle_run_events)
    app.router.add_post("/v1/runs/{run_id}/approval", server._handle_run_approval)
    app.router.add_post("/v1/runs/{run_id}/stop", server._handle_stop_run)

    # ------------------------------------------------------------------
    # 3. Register SkillHub routes from hub_api_server.py
    # ------------------------------------------------------------------
    hub_app = make_hub_app()
    for route in hub_app.router.routes():
        app.router.add_route(
            route.method,
            route.resource.canonical,
            route.handler,
            name=route.name,
        )

    # ------------------------------------------------------------------
    # 4. Port conflict check
    # ------------------------------------------------------------------
    try:
        with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect((HOST, PORT))
        print(f"[ERROR] Port {PORT} already in use.")
        sys.exit(1)
    except (ConnectionRefusedError, OSError):
        pass  # port is free

    # ------------------------------------------------------------------
    # 5. Start server
    # ------------------------------------------------------------------
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()

    print("=" * 60)
    print("Combined API server running on http://127.0.0.1:8643")
    print()
    print("Management endpoints:")
    print("  GET  /api/security/mode    POST /api/security/mode")
    print("  GET  /api/sandbox           POST /api/sandbox")
    print("  GET  /api/workdir           POST /api/workdir")
    print("  GET  /api/audit/log         DELETE /api/audit/log")
    print()
    print("SkillHub endpoints:")
    print("  GET  /api/skills            GET  /api/skills/installed")
    print("  POST /api/skills/install    POST /api/skills/uninstall")
    print("  POST /api/skills/upload")
    print()
    print("Press Ctrl+C to stop.")
    print("=" * 60)

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        await runner.cleanup()
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")
