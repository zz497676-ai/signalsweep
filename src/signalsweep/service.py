"""Small HTTP entry point for event-driven Taskmaster runs.

The service deliberately uses Python's standard library so the core workflow
can be tested and deployed before Streamlit, Gemini, or Firestore are added.
Cloud Run can send traffic to ``POST /run`` and use ``GET /healthz`` as its
startup/liveness check.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from typing import Any
from urllib.parse import urlsplit

from .pipeline import SAFE_APPROVED_ACTIONS, run_pipeline
from .state import JobStore, create_job_store

MAX_REQUEST_BYTES = 5 * 1024 * 1024
_JOB_STORE: JobStore = create_job_store()
_JOB_LOCK = Lock()
_REVIEW_DECISIONS = {
    "approve_normalized_copy": ("approved", "complete"),
    "reject_run": ("rejected", "reject"),
}


class EventConflictError(ValueError):
    """Raised when an event ID is reused for different input data."""


def _request_fingerprint(csv_text: str, dataset_name: str) -> str:
    """Create a stable, non-reversible identity for one submitted request."""

    material = f"{dataset_name}\0{csv_text}".encode()
    return hashlib.sha256(material).hexdigest()


def _record_fingerprint(record: dict[str, Any]) -> str | None:
    """Read or reconstruct a request fingerprint from a stored job."""

    fingerprint = record.get("input_fingerprint")
    if isinstance(fingerprint, str) and fingerprint:
        return fingerprint

    source = record.get("input")
    if not isinstance(source, dict):
        return None
    csv_text = source.get("csv_text")
    dataset_name = source.get("dataset_name")
    if not isinstance(csv_text, str) or not isinstance(dataset_name, str):
        return None
    return _request_fingerprint(csv_text, dataset_name)


def health_payload() -> dict[str, str]:
    """Return a stable health response for local checks and Cloud Run."""

    return {"status": "ok", "service": "signalsweep", "version": "0.3.0"}


def run_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate an event payload and run one complete Taskmaster workflow."""

    if not isinstance(payload, dict):
        raise ValueError(  # noqa: TRY004 - the HTTP layer maps validation to 400.
            "The request body must be a JSON object."
        )

    csv_text = payload.get("csv_text")
    if not isinstance(csv_text, str) or not csv_text.strip():
        raise ValueError("The request must include non-empty string field 'csv_text'.")

    dataset_name = payload.get("dataset_name", "uploaded.csv")
    if not isinstance(dataset_name, str) or not dataset_name.strip():
        raise ValueError("'dataset_name' must be a non-empty string when provided.")

    event_id = payload.get("event_id")
    if event_id is not None and (
        not isinstance(event_id, str)
        or not event_id.strip()
        or len(event_id) > 128
        or not re.fullmatch(r"[A-Za-z0-9._-]+", event_id)
    ):
        raise ValueError(
            "'event_id' must use letters, numbers, '.', '_' or '-' and be at most 128 characters."
        )

    normalized_dataset_name = dataset_name.strip()
    fingerprint = _request_fingerprint(csv_text, normalized_dataset_name)

    if event_id is not None:
        # Event delivery can be retried. Treat the event ID as an idempotency
        # key, while rejecting accidental reuse for different input data.
        with _JOB_LOCK:
            existing = _JOB_STORE.get(event_id)
            if existing is not None and "response" in existing:
                previous_fingerprint = _record_fingerprint(existing)
                if previous_fingerprint and previous_fingerprint != fingerprint:
                    raise EventConflictError(
                        f"event_id {event_id!r} already exists for a different request."
                    )
                return existing["response"]

            result = run_pipeline(csv_text, normalized_dataset_name)
            response = result.to_dict()
            response["event_id"] = event_id
            _JOB_STORE.put(
                event_id,
                {
                    "response": response,
                    "input_fingerprint": fingerprint,
                    "input": {
                        "csv_text": csv_text,
                        "dataset_name": normalized_dataset_name,
                    },
                },
            )
            return response

    result = run_pipeline(csv_text, normalized_dataset_name)
    response = result.to_dict()
    response["event_id"] = None
    return response


def _append_review_to_report(
    report_markdown: str,
    workflow_status: str,
    decision: str,
    note: str,
    approved_actions: list[str],
) -> str:
    """Keep the downloadable report consistent with the final review state."""

    updated_report = re.sub(
        r"- Workflow status: \*\*[^*]+\*\*",
        f"- Workflow status: **{workflow_status}**",
        report_markdown,
        count=1,
    )
    actions_text = ", ".join(f"`{action}`" for action in approved_actions) or "none"
    return updated_report.rstrip() + "\n\n## Human review\n\n" + "\n".join(
        [
            f"- Decision: **{decision}**",
            f"- Approved actions: {actions_text}",
            f"- Note: {note}",
        ]
    ) + "\n"


def review_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Resume a paused run after an explicit human decision."""

    if not isinstance(payload, dict):
        raise ValueError(  # noqa: TRY004 - the HTTP layer maps validation to 400.
            "The request body must be a JSON object."
        )

    event_id = payload.get("event_id")
    decision = payload.get("decision")
    note = payload.get("note")
    if not isinstance(event_id, str) or not event_id.strip():
        raise ValueError("The review request must include 'event_id'.")
    if not isinstance(decision, str) or decision not in _REVIEW_DECISIONS:
        allowed = ", ".join(sorted(_REVIEW_DECISIONS))
        raise ValueError(f"'decision' must be one of: {allowed}.")
    if not isinstance(note, str) or not note.strip() or len(note) > 2_000:
        raise ValueError("The review request must include a note of at most 2000 characters.")

    approved_actions = payload.get("approved_actions", [])
    if not isinstance(approved_actions, list) or not all(
        isinstance(action, str) for action in approved_actions
    ):
        raise ValueError("'approved_actions' must be a list of action names.")
    unknown_actions = set(approved_actions) - SAFE_APPROVED_ACTIONS
    if unknown_actions:
        allowed = ", ".join(sorted(SAFE_APPROVED_ACTIONS))
        raise ValueError(f"Unsupported approved action(s); allowed: {allowed}.")
    if decision == "reject_run" and approved_actions:
        raise ValueError("A rejected run cannot include approved actions.")

    with _JOB_LOCK:
        record = _JOB_STORE.get(event_id)
        if record is None or "response" not in record:
            raise KeyError(f"No stored run found for event_id {event_id!r}.")
        stored = record["response"]
        if stored.get("workflow_status") != "needs_review":
            raise ValueError("This run is not waiting for human review.")

        updated = json.loads(json.dumps(stored))
        workflow_status, action_decision = _REVIEW_DECISIONS[decision]
        if decision == "approve_normalized_copy" and approved_actions:
            source = record.get("input")
            if source is None:
                raise KeyError(f"Original input is no longer available for event_id {event_id!r}.")
            rerun = run_pipeline(
                source["csv_text"],
                source["dataset_name"],
                approved_actions=approved_actions,
            ).to_dict()
            for key in ("plan", "profile", "issues", "anomalies", "cleaned_csv", "report_markdown"):
                updated[key] = rerun[key]
            updated["actions"] = rerun["actions"]
            updated["events"].append(
                {
                    "sequence": len(updated["events"]) + 1,
                    "step": "apply_approved_actions",
                    "status": "completed",
                    "message": ", ".join(approved_actions),
                }
            )
        updated["workflow_status"] = workflow_status
        updated["review"] = {
            "decision": decision,
            "note": note.strip(),
            "approved_actions": approved_actions,
        }
        updated["actions"].append(
            {
                "action": "human_review",
                "decision": action_decision,
                "priority": "high",
                "reason": note.strip(),
                "requires_human_review": False,
            }
        )
        updated["events"].append(
            {
                "sequence": len(updated["events"]) + 1,
                "step": "human_review",
                "status": "completed" if workflow_status == "approved" else "rejected",
                "message": note.strip(),
            }
        )
        updated["report_markdown"] = _append_review_to_report(
            updated["report_markdown"],
            workflow_status,
            decision,
            note.strip(),
            approved_actions,
        )
        reviewed_record: dict[str, Any] = {"response": updated}
        fingerprint = _record_fingerprint(record)
        if fingerprint:
            # Keep only a non-reversible identity after review; the original
            # CSV is no longer needed once the decision has been recorded.
            reviewed_record["input_fingerprint"] = fingerprint
        _JOB_STORE.put(event_id, reviewed_record)
        return updated


def get_job_request(event_id: str) -> dict[str, Any]:
    """Read the latest public result for a stored Taskmaster job."""

    if not isinstance(event_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", event_id):
        raise ValueError("'event_id' must use letters, numbers, '.', '_' or '-'.")
    with _JOB_LOCK:
        record = _JOB_STORE.get(event_id)
    if record is None or "response" not in record:
        raise KeyError(f"No stored run found for event_id {event_id!r}.")
    return record["response"]


class SignalSweepHandler(BaseHTTPRequestHandler):
    """HTTP adapter around the dependency-light workflow."""

    server_version = "SignalSweep/0.3"

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/healthz":
            self._send_json(HTTPStatus.OK, health_payload())
            return
        if path.startswith("/jobs/"):
            try:
                response = get_job_request(path.removeprefix("/jobs/"))
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            except KeyError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return
            self._send_json(HTTPStatus.OK, response)
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path not in {"/run", "/review"}:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return

        content_length_header = self.headers.get("Content-Length")
        try:
            content_length = int(content_length_header or "0")
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_content_length"})
            return

        if content_length <= 0:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "empty_request_body"})
            return
        if content_length > MAX_REQUEST_BYTES:
            self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "request_too_large"})
            return

        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            response = run_request(payload) if path == "/run" else review_request(payload)
        except EventConflictError as exc:
            self._send_json(HTTPStatus.CONFLICT, {"error": str(exc)})
            return
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        except KeyError as exc:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            return
        except Exception:  # noqa: BLE001 - keep the HTTP server from leaking internals.
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "workflow_failed"})
            return

        self._send_json(HTTPStatus.OK, response)

    def log_message(self, format: str, *args: Any) -> None:
        """Keep local logs useful without exposing uploaded CSV contents."""

        super().log_message(format, *args)


def main() -> None:
    """Start the local/Cloud Run HTTP server."""

    port = int(os.getenv("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), SignalSweepHandler)
    print(f"SignalSweep service listening on http://0.0.0.0:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
