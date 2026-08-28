"""Small client for invoking SignalSweep's private ADK Cloud Run service."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

DEFAULT_CLOUD_AGENT_URL = "https://signalsweep-agent-5omgubz3cq-uc.a.run.app"
DEFAULT_APP_NAME = "signalsweep"
DEFAULT_USER_ID = "signalsweep-streamlit"
DEFAULT_TIMEOUT_SECONDS = 120.0


class CloudAgentError(RuntimeError):
    """Raised when the private Cloud Run Agent cannot complete a request."""


JsonRequester = Callable[[str, str, Any, float], Any]
TokenProvider = Callable[[str], str]


def configured_agent_url() -> str:
    """Return the deployed Agent URL, allowing an environment override."""

    return os.getenv("SIGNALSWEEP_AGENT_URL", DEFAULT_CLOUD_AGENT_URL).strip()


def _origin(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Cloud Agent URL must be an absolute http(s) URL.")
    return f"{parsed.scheme}://{parsed.netloc}"


def _identity_token(audience: str, gcloud_bin: str = "gcloud") -> str:
    """Use the user's existing gcloud login without exposing the token."""

    commands = [
        [gcloud_bin, "auth", "print-identity-token", f"--audiences={audience}"],
        [gcloud_bin, "auth", "print-identity-token"],
    ]
    last_returncode = 1
    try:
        for command in commands:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
                timeout=15,
            )
            last_returncode = completed.returncode
            token = completed.stdout.strip()
            if completed.returncode == 0 and token:
                return token
    except FileNotFoundError as exc:
        raise CloudAgentError("找不到 gcloud，请先安装 Google Cloud CLI。") from exc
    except subprocess.TimeoutExpired as exc:
        raise CloudAgentError("获取 Google Cloud 登录令牌超时。") from exc

    if last_returncode != 0:
        raise CloudAgentError("无法获取 Google Cloud 登录令牌，请先执行 gcloud auth login。")
    raise CloudAgentError("Google Cloud 登录令牌为空。")


def _json_request(url: str, token: str, payload: Any, timeout: float) -> Any:
    """Send one authenticated JSON request without logging uploaded data."""

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw_body = response.read()
    except HTTPError as exc:
        raise CloudAgentError(f"Cloud Agent 请求失败（HTTP {exc.code}）。") from exc
    except URLError as exc:
        raise CloudAgentError("无法连接 Cloud Run Agent，请检查网络或服务状态。") from exc
    except TimeoutError as exc:
        raise CloudAgentError("Cloud Run Agent 请求超时。") from exc

    try:
        return json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CloudAgentError("Cloud Run Agent 返回了无法解析的响应。") from exc


def build_csv_prompt(csv_text: str, dataset_name: str) -> str:
    """Ask the ADK agent to call the deterministic Taskmaster tool."""

    if not csv_text.strip():
        raise ValueError("CSV content cannot be empty.")
    return "\n".join(
        [
            "请处理下面这份 CSV，并完成 SignalSweep 的 Taskmaster 工作流。",
            "必须先调用 taskmaster_workflow_tool，不要只给建议。",
            "工具返回的结构化结果是事实来源；请在工具完成后用不超过三句话总结。",
            f"数据集名称：{dataset_name}",
            "CSV 内容开始",
            csv_text,
            "CSV 内容结束",
        ]
    )


@dataclass(frozen=True)
class CloudAgentClient:
    """Invoke an ADK API server using the local user's gcloud identity."""

    base_url: str
    app_name: str = DEFAULT_APP_NAME
    user_id: str = DEFAULT_USER_ID
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    token_provider: TokenProvider | None = None
    gcloud_bin: str = "gcloud"
    requester: JsonRequester = _json_request

    def __post_init__(self) -> None:
        object.__setattr__(self, "base_url", self.base_url.rstrip("/"))
        _origin(self.base_url)

    def _get_token(self) -> str:
        audience = _origin(self.base_url)
        if self.token_provider is not None:
            return self.token_provider(audience)
        return _identity_token(audience, self.gcloud_bin)

    def run_csv(self, csv_text: str, dataset_name: str) -> dict[str, Any]:
        """Create an ADK session and run the Taskmaster prompt."""

        token = self._get_token()
        app = quote(self.app_name, safe="")
        user = quote(self.user_id, safe="")
        session_url = f"{self.base_url}/apps/{app}/users/{user}/sessions"
        session = self.requester(session_url, token, {}, self.timeout)
        if not isinstance(session, dict) or not isinstance(session.get("id"), str):
            raise CloudAgentError("Cloud Run Agent 没有返回有效的会话 ID。")

        run_response = self.requester(
            f"{self.base_url}/run",
            token,
            {
                "app_name": self.app_name,
                "user_id": self.user_id,
                "session_id": session["id"],
                "new_message": {
                    "role": "user",
                    "parts": [{"text": build_csv_prompt(csv_text, dataset_name)}],
                },
            },
            self.timeout,
        )
        if not isinstance(run_response, list):
            raise CloudAgentError("Cloud Run Agent 返回了无效的事件列表。")
        return {"events": run_response}


def summarize_cloud_response(response: dict[str, Any]) -> dict[str, Any]:
    """Keep the UI trace useful without displaying CSV arguments or responses."""

    events = response.get("events", [])
    if not isinstance(events, list):
        events = []

    tool_calls: list[str] = []
    tool_results: list[str] = []
    assistant_text: list[str] = []
    model_version = ""
    for event in events:
        if not isinstance(event, dict):
            continue
        model_version = model_version or str(
            event.get("modelVersion") or event.get("model_version") or ""
        )
        content = event.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts", [])
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict):
                continue
            function_call = part.get("functionCall") or part.get("function_call")
            if isinstance(function_call, dict) and isinstance(function_call.get("name"), str):
                tool_calls.append(function_call["name"])
            function_response = part.get("functionResponse") or part.get("function_response")
            if isinstance(function_response, dict) and isinstance(function_response.get("name"), str):
                tool_results.append(function_response["name"])
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                assistant_text.append(text.strip())

    return {
        "status": "completed",
        "model_version": model_version or "unknown",
        "event_count": len(events),
        "tool_calls": sorted(set(tool_calls)),
        "tool_results": sorted(set(tool_results)),
        "assistant_text": "\n".join(assistant_text)[-2_000:],
    }
