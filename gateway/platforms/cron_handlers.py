"""
Cron job management HTTP handlers for the API server.

Implements the /api/jobs/* endpoints that were registered as route stubs in
api_server.py but left unimplemented.  Also provides skills listing and
job-results endpoints.

Handlers get the APIServerAdapter via ``request.app["api_server_adapter"]``.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    web = None

from cron import jobs as cron_jobs
from gateway.audit_log import (
    JOB_CREATE,
    JOB_DELETE,
    JOB_PAUSE,
    JOB_RESUME,
    JOB_RUN,
    JOB_UPDATE,
    log_audit_event,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_adapter(request: "web.Request") -> Any:
    """Return the APIServerAdapter instance from the app."""
    return request.app.get("api_server_adapter")


def _check_auth(request: "web.Request") -> Optional["web.Response"]:
    """Delegate auth check to the adapter."""
    adapter = _get_adapter(request)
    if adapter and hasattr(adapter, "_check_auth"):
        return adapter._check_auth(request)
    return None


def _ok(data: Any, status: int = 200) -> "web.Response":
    """Return a success JSON response."""
    return web.json_response({"success": True, "data": data}, status=status)


def _error(message: str, status: int = 400) -> "web.Response":
    """Return an error JSON response."""
    return web.json_response({"success": False, "error": message}, status=status)


async def _parse_json(request: "web.Request") -> Any:
    """Parse JSON body with error handling."""
    try:
        return await request.json()
    except (json.JSONDecodeError, Exception):
        return None


async def _read_output_for_job(job_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Read the most recent output files for a cron job.

    Output is stored in ~/.hermes/cron/output/{job_id}/{timestamp}.md
    """
    HERMES_DIR = cron_jobs.HERMES_DIR
    output_dir = HERMES_DIR / "cron" / "output" / job_id
    if not output_dir.exists():
        return []

    files = sorted(output_dir.glob("*.md"), reverse=True)
    results = []
    for f in files[:limit]:
        ts = f.stem.replace("_", "T")
        try:
            content = f.read_text(encoding="utf-8")
        except Exception:
            content = "(failed to read output)"
        results.append({
            "run_at": ts,
            "output": content,
            "output_preview": content[:300],
        })
    return results


# ---------------------------------------------------------------------------
# Cron Job Handlers
# ---------------------------------------------------------------------------

async def handle_list_jobs(request: "web.Request") -> "web.Response":
    """GET /api/jobs — list all cron jobs (optionally including disabled)."""
    auth_err = _check_auth(request)
    if auth_err:
        return auth_err

    try:
        include_disabled = request.query.get("all", "").lower() in ("true", "1")
        jobs = cron_jobs.list_jobs(include_disabled=include_disabled)
        return _ok({"jobs": jobs, "total": len(jobs)})
    except Exception as e:
        logger.exception("Failed to list jobs")
        return _error(str(e), 500)


async def handle_create_job(request: "web.Request") -> "web.Response":
    """POST /api/jobs — create a new cron job."""
    auth_err = _check_auth(request)
    if auth_err:
        return auth_err

    body = await _parse_json(request)
    if body is None:
        return _error("Invalid JSON in request body")

    prompt = body.get("prompt", "")
    schedule = body.get("schedule", "")
    if not schedule:
        return _error("'schedule' is required")

    try:
        job = cron_jobs.create_job(
            prompt=prompt or None,
            schedule=schedule,
            name=body.get("name"),
            repeat=body.get("repeat"),
            deliver=body.get("deliver", "local"),
            origin={"source": "web-ui"},
            skills=body.get("skills"),
            model=body.get("model"),
            provider=body.get("provider"),
            script=body.get("script"),
            workdir=body.get("workdir"),
            profile=body.get("profile"),
            no_agent=bool(body.get("no_agent", False)),
            enabled_toolsets=body.get("enabled_toolsets"),
        )
        log_audit_event(JOB_CREATE, detail={"job_id": job["id"], "name": job.get("name")})
        return _ok(job, 201)
    except ValueError as e:
        return _error(str(e))
    except Exception as e:
        logger.exception("Failed to create job")
        return _error(str(e), 500)


async def handle_get_job(request: "web.Request") -> "web.Response":
    """GET /api/jobs/{job_id} — get a single job by ID."""
    auth_err = _check_auth(request)
    if auth_err:
        return auth_err

    job_id = request.match_info.get("job_id", "")
    if not job_id:
        return _error("Missing job_id")

    try:
        job = cron_jobs.get_job(job_id)
        if not job:
            return _error(f"Job '{job_id}' not found", 404)
        return _ok(job)
    except Exception as e:
        logger.exception("Failed to get job")
        return _error(str(e), 500)


async def handle_update_job(request: "web.Request") -> "web.Response":
    """PATCH /api/jobs/{job_id} — update a cron job."""
    auth_err = _check_auth(request)
    if auth_err:
        return auth_err

    job_id = request.match_info.get("job_id", "")
    if not job_id:
        return _error("Missing job_id")

    body = await _parse_json(request)
    if body is None:
        return _error("Invalid JSON in request body")

    try:
        # Map frontend field names to update_job() expected keys
        updates = {}
        for key in ("prompt", "name", "repeat", "deliver", "model",
                     "provider", "script", "workdir", "profile",
                     "enabled_toolsets"):
            if key in body:
                updates[key] = body[key]

        if "schedule" in body:
            updates["schedule"] = body["schedule"]

        if "skills" in body:
            updates["skills"] = body["skills"]

        if "no_agent" in body:
            updates["no_agent"] = bool(body["no_agent"])

        job = cron_jobs.update_job(job_id, updates)
        if not job:
            return _error(f"Job '{job_id}' not found", 404)
        log_audit_event(JOB_UPDATE, detail={"job_id": job_id})
        return _ok(job)
    except ValueError as e:
        return _error(str(e))
    except Exception as e:
        logger.exception("Failed to update job")
        return _error(str(e), 500)


async def handle_delete_job(request: "web.Request") -> "web.Response":
    """DELETE /api/jobs/{job_id} — delete a cron job."""
    auth_err = _check_auth(request)
    if auth_err:
        return auth_err

    job_id = request.match_info.get("job_id", "")
    if not job_id:
        return _error("Missing job_id")

    try:
        removed = cron_jobs.remove_job(job_id)
        if not removed:
            return _error(f"Job '{job_id}' not found", 404)
        log_audit_event(JOB_DELETE, detail={"job_id": job_id})
        return _ok({"deleted": True, "job_id": job_id})
    except Exception as e:
        logger.exception("Failed to delete job")
        return _error(str(e), 500)


async def handle_pause_job(request: "web.Request") -> "web.Response":
    """POST /api/jobs/{job_id}/pause — pause a cron job."""
    auth_err = _check_auth(request)
    if auth_err:
        return auth_err

    job_id = request.match_info.get("job_id", "")
    if not job_id:
        return _error("Missing job_id")

    try:
        body = await _parse_json(request)
        reason = body.get("reason") if body else None
        job = cron_jobs.pause_job(job_id, reason=reason)
        if not job:
            return _error(f"Job '{job_id}' not found", 404)
        log_audit_event(JOB_PAUSE, detail={"job_id": job_id, "reason": reason})
        return _ok(job)
    except Exception as e:
        logger.exception("Failed to pause job")
        return _error(str(e), 500)


async def handle_resume_job(request: "web.Request") -> "web.Response":
    """POST /api/jobs/{job_id}/resume — resume a paused cron job."""
    auth_err = _check_auth(request)
    if auth_err:
        return auth_err

    job_id = request.match_info.get("job_id", "")
    if not job_id:
        return _error("Missing job_id")

    try:
        job = cron_jobs.resume_job(job_id)
        if not job:
            return _error(f"Job '{job_id}' not found", 404)
        log_audit_event(JOB_RESUME, detail={"job_id": job_id})
        return _ok(job)
    except Exception as e:
        logger.exception("Failed to resume job")
        return _error(str(e), 500)


async def handle_run_job(request: "web.Request") -> "web.Response":
    """POST /api/jobs/{job_id}/run — trigger a cron job to run on next tick."""
    auth_err = _check_auth(request)
    if auth_err:
        return auth_err

    job_id = request.match_info.get("job_id", "")
    if not job_id:
        return _error("Missing job_id")

    try:
        job = cron_jobs.trigger_job(job_id)
        if not job:
            return _error(f"Job '{job_id}' not found", 404)
        log_audit_event(JOB_RUN, detail={"job_id": job_id})
        return _ok({"triggered": True, "job_id": job_id, "next_run_at": job.get("next_run_at")})
    except Exception as e:
        logger.exception("Failed to trigger job")
        return _error(str(e), 500)


# ---------------------------------------------------------------------------
# Results & Dashboard Handlers
# ---------------------------------------------------------------------------

async def handle_job_results(request: "web.Request") -> "web.Response":
    """GET /api/jobs/{job_id}/results — get run results for a job.

    Query params:
        limit (int): max results to return (default 10)
    """
    auth_err = _check_auth(request)
    if auth_err:
        return auth_err

    job_id = request.match_info.get("job_id", "")
    if not job_id:
        return _error("Missing job_id")

    try:
        limit_str = request.query.get("limit", "10")
        limit = max(1, min(int(limit_str), 100))
    except (ValueError, TypeError):
        limit = 10

    try:
        # Verify the job exists
        job = cron_jobs.get_job(job_id)
        if not job:
            return _error(f"Job '{job_id}' not found", 404)

        results = await _read_output_for_job(job_id, limit=limit)
        return _ok({"job_id": job_id, "results": results, "total": len(results)})
    except Exception as e:
        logger.exception("Failed to read job results")
        return _error(str(e), 500)


async def handle_job_dashboard(request: "web.Request") -> "web.Response":
    """GET /api/jobs/dashboard — aggregate dashboard data for the home page.

    Returns all jobs with their latest output preview, enabling the home page
    to show a summary at a glance.
    """
    auth_err = _check_auth(request)
    if auth_err:
        return auth_err

    try:
        jobs = cron_jobs.list_jobs(include_disabled=True)
        dashboard_items = []
        for job in jobs:
            job_id = job["id"]
            latest = None
            try:
                results = await _read_output_for_job(job_id, limit=1)
                if results:
                    latest = results[0]
            except Exception:
                pass

            dashboard_items.append({
                "job_id": job_id,
                "name": job.get("name"),
                "schedule": job.get("schedule_display"),
                "state": job.get("state"),
                "enabled": job.get("enabled", True),
                "last_run_at": job.get("last_run_at"),
                "last_status": job.get("last_status"),
                "next_run_at": job.get("next_run_at"),
                "skills": job.get("skills", []),
                "latest_run": latest,
            })

        active_count = sum(1 for j in dashboard_items if j.get("enabled") and j.get("state") not in ("paused", "completed"))
        return _ok({
            "jobs": dashboard_items,
            "total": len(dashboard_items),
            "active": active_count,
        })
    except Exception as e:
        logger.exception("Failed to build dashboard")
        return _error(str(e), 500)


async def handle_latest_results(request: "web.Request") -> "web.Response":
    """GET /api/jobs/results/latest — get the latest run result for every job.

    Returns a list of all jobs (including disabled) with their most recent
    execution result, enabling a "last execution summary" view across all
    scheduled jobs in a single call.
    """
    auth_err = _check_auth(request)
    if auth_err:
        return auth_err

    try:
        jobs = cron_jobs.list_jobs(include_disabled=True)
        items = []
        for job in jobs:
            job_id = job["id"]
            latest = None
            try:
                results = await _read_output_for_job(job_id, limit=1)
                if results:
                    latest = results[0]
            except Exception:
                pass

            items.append({
                "job_id": job_id,
                "name": job.get("name"),
                "schedule": job.get("schedule_display"),
                "state": job.get("state"),
                "enabled": job.get("enabled", True),
                "last_run_at": job.get("last_run_at"),
                "last_status": job.get("last_status"),
                "next_run_at": job.get("next_run_at"),
                "latest_run": latest,
            })

        return _ok({"jobs": items, "total": len(items)})
    except Exception as e:
        logger.exception("Failed to build latest results list")
        return _error(str(e), 500)


# ---------------------------------------------------------------------------
# Skills List Handler
# ---------------------------------------------------------------------------

async def handle_list_skills(request: "web.Request") -> "web.Response":
    """GET /api/cron/skills — list all available skills for the cron job creation form.

    Returns skills grouped by category so the frontend can render a categorized
    multi-select dropdown.
    """
    auth_err = _check_auth(request)
    if auth_err:
        return auth_err

    try:
        from tools.skills_tool import _find_all_skills

        all_skills = _find_all_skills(skip_disabled=False)
        # Build a categorized structure
        categories: Dict[str, list] = {}
        for skill in all_skills:
            cat = skill.get("category", "uncategorized") or "uncategorized"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append({
                "name": skill["name"],
                "description": skill.get("description", ""),
            })

        # Sort skills within each category
        for cat_list in categories.values():
            cat_list.sort(key=lambda s: s["name"])

        # Sort categories
        sorted_categories = [
            {"category": cat, "skills": categories[cat]}
            for cat in sorted(categories.keys())
        ]

        return _ok({
            "categories": sorted_categories,
            "total": len(all_skills),
        })
    except Exception as e:
        logger.exception("Failed to list skills")
        return _error(str(e), 500)
