"""
audit_logger.py
================
ReRoutz AI — Immutable Audit Trail (Supabase / PostgreSQL)

Ships structured audit records to a Supabase `audit_logs` table in a
fire-and-forget background thread so the FastAPI response latency is
NEVER affected by the logging call.

Table schema (create this once in the Supabase SQL editor):
--------------------------------------------------------------
    create table audit_logs (
        id          bigint generated always as identity primary key,
        created_at  timestamptz default now() not null,
        event_type  text        not null,
        payload     jsonb       not null
    );

    -- Optional but recommended: index for fast filtering by event type
    create index on audit_logs (event_type);
    create index on audit_logs using gin (payload);
--------------------------------------------------------------

Environment variables (set in docker-compose or .env):
    SUPABASE_URL   — e.g. https://xyzcompany.supabase.co
    SUPABASE_KEY   — your project's anon or service-role key

Usage:
    from audit_logger import audit_logger

    audit_logger.log("diversion_query", {
        "target_lat": 12.97,
        "target_lon": 77.59,
        ...
    })
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# Official Supabase Python client.
# Falls back to a no-op if the package isn't installed so dev environments
# without credentials can still run the backend.
try:
    from supabase import create_client, Client as SupabaseClient
    _SUPABASE_AVAILABLE = True
except ImportError:
    _SUPABASE_AVAILABLE = False
    print("[AuditLogger] ⚠️  'supabase' package not installed — audit logging disabled.")

_SUPABASE_URL = os.getenv("SUPABASE_URL", "")
_SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

_AUDIT_TABLE = "audit_logs"


def _build_client() -> "SupabaseClient | None":
    """
    Build and return a Supabase client, or None if credentials are missing
    or the package is not installed.
    """
    if not _SUPABASE_AVAILABLE:
        return None
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        print("[AuditLogger] ⚠️  SUPABASE_URL / SUPABASE_KEY env vars not set — audit logging disabled.")
        return None
    try:
        client = create_client(_SUPABASE_URL, _SUPABASE_KEY)
        print(f"[AuditLogger] ✅ Supabase client initialised → {_SUPABASE_URL}")
        return client
    except Exception as exc:
        print(f"[AuditLogger] ⚠️  Could not create Supabase client: {exc}")
        return None


class AuditLogger:
    """
    Thread-safe, fire-and-forget audit logger for ReRoutz AI.

    Every call to .log() spawns a daemon thread that inserts a row into
    the Supabase `audit_logs` table.  The calling FastAPI handler returns
    immediately — the DB write never blocks the response.

    Row layout
    ----------
    event_type : text   — short identifier, e.g. "diversion_query"
    payload    : jsonb  — entire audit dict (timestamp, audit_id, inputs,
                          outputs, response_time_ms, …)
    """

    def __init__(self) -> None:
        self._client: "SupabaseClient | None" = _build_client()
        self._lock = threading.Lock()

    def _get_client(self) -> "SupabaseClient | None":
        """Lazy reconnect: if the client is None, try to rebuild it once."""
        with self._lock:
            if self._client is None:
                self._client = _build_client()
            return self._client

    def _ship(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Runs in a background daemon thread — never called directly."""
        client = self._get_client()
        if client is None:
            return  # credentials missing or package absent — silently skip

        row = {
            "event_type": event_type,
            # `payload` is the full audit dict stored as JSONB.
            # supabase-py accepts a plain dict; the driver serialises it.
            "payload": payload,
        }

        try:
            client.table(_AUDIT_TABLE).insert(row).execute()
        except Exception as exc:
            # Never crash the application because of a logging failure.
            with self._lock:
                self._client = None  # force reconnect on next attempt
            print(f"[AuditLogger] ⚠️  Failed to insert audit row: {exc}")

    def log(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        Non-blocking audit log entry point.

        Enriches the payload with standard fields (@timestamp, audit_id),
        then ships the row to Supabase in a daemon thread.

        Parameters
        ----------
        event_type : str
            Short identifier, e.g. "diversion_query", "route_query",
            "deployment_prediction".
        payload : dict
            Structured data for this event. Merged with standard fields
            before being stored in the JSONB `payload` column.
        """
        # Build the full payload dict — same shape as before, stored as JSONB
        full_payload: Dict[str, Any] = {
            "@timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "audit_id": str(uuid.uuid4()),
            "system": "ReRoutz-ai",
            **payload,
        }

        t = threading.Thread(
            target=self._ship,
            args=(event_type, full_payload),
            daemon=True,
            name=f"audit-{event_type}",
        )
        t.start()


# ─────────────────────────────────────────────
# Module-level singleton — import and use anywhere:
#   from audit_logger import audit_logger
# ─────────────────────────────────────────────
audit_logger = AuditLogger()
