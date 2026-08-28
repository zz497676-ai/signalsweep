import json
import subprocess
import unittest
from unittest.mock import patch

import signalsweep.cloud_agent as cloud_agent_module
from signalsweep.cloud_agent import (
    CloudAgentClient,
    build_csv_prompt,
    summarize_cloud_response,
)


class FakeRequester:
    def __init__(self):
        self.calls = []

    def __call__(self, url, token, payload, timeout):
        self.calls.append((url, token, payload, timeout))
        if url.endswith("/sessions"):
            return {"id": "session-001"}
        return [
            {
                "modelVersion": "gemini-3.5-flash",
                "content": {
                    "parts": [
                        {
                            "functionCall": {
                                "name": "taskmaster_workflow_tool",
                                "args": {"csv_text": "private csv"},
                            }
                        }
                    ]
                },
            },
            {
                "content": {
                    "parts": [{"text": "已完成数据质量检查。"}],
                },
            },
        ]


class CloudAgentClientTests(unittest.TestCase):
    def test_identity_token_falls_back_for_user_credentials(self):
        with patch(
            "signalsweep.cloud_agent.subprocess.run",
            side_effect=[
                subprocess.CompletedProcess(
                    args=[],
                    returncode=1,
                    stdout="",
                    stderr="Invalid account type for --audiences",
                ),
                subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout="user-token\n",
                    stderr="",
                ),
            ],
        ) as run:
            token = cloud_agent_module._identity_token("https://agent.example", "gcloud")

        self.assertEqual(token, "user-token")
        self.assertEqual(run.call_count, 2)
        self.assertIn("--audiences=https://agent.example", run.call_args_list[0].args[0])
        self.assertNotIn("--audiences", run.call_args_list[1].args[0])

    def test_run_csv_creates_session_and_sends_prompt(self):
        requester = FakeRequester()
        client = CloudAgentClient(
            base_url="https://agent.example",
            token_provider=lambda audience: f"token-for:{audience}",
            requester=requester,
        )

        response = client.run_csv("id,amount\n1,10\n", "orders.csv")

        self.assertEqual(response["events"][0]["modelVersion"], "gemini-3.5-flash")
        self.assertEqual(len(requester.calls), 2)
        self.assertEqual(requester.calls[0][0], "https://agent.example/apps/signalsweep/users/signalsweep-streamlit/sessions")
        self.assertEqual(requester.calls[0][1], "token-for:https://agent.example")
        run_payload = requester.calls[1][2]
        prompt = run_payload["new_message"]["parts"][0]["text"]
        self.assertIn("orders.csv", prompt)
        self.assertIn("id,amount", prompt)
        self.assertEqual(run_payload["session_id"], "session-001")

    def test_summary_does_not_expose_tool_arguments(self):
        summary = summarize_cloud_response(
            {
                "events": FakeRequester()("/run", "token", {}, 1),
            }
        )

        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["model_version"], "gemini-3.5-flash")
        self.assertEqual(summary["tool_calls"], ["taskmaster_workflow_tool"])
        self.assertNotIn("private csv", json.dumps(summary, ensure_ascii=False))
        self.assertIn("已完成数据质量检查", summary["assistant_text"])

    def test_prompt_rejects_empty_csv(self):
        with self.assertRaises(ValueError):
            build_csv_prompt("", "empty.csv")

    def test_client_rejects_non_http_url(self):
        with self.assertRaises(ValueError):
            CloudAgentClient("not-a-url")


if __name__ == "__main__":
    unittest.main()
