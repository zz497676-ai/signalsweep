import unittest

import signalsweep.service as service_module
from signalsweep.pipeline import run_pipeline
from signalsweep.service import (
    get_job_request,
    health_payload,
    review_request,
    run_request,
)

SAMPLE_CSV = """date,category,amount,status
2026-08-01,software,120,paid
2026-08-02,software,135,paid
2026-08-03,hardware,90,paid
2026-08-04,hardware,110,
2026-08-05,software,128,paid
2026-08-06,software,142,paid
2026-08-07,hardware,9999,paid
2026-08-08,hardware,105,paid
2026-08-09,software,118,paid
2026-08-10,software,130,paid
2026-08-11,software,125,paid
2026-08-11,software,125,paid
"""

CLEAN_CSV = """id,amount,status
1,10,paid
2,11,paid
3,12,paid
4,13,paid
"""


class PipelineTests(unittest.TestCase):
    def test_pipeline_profiles_checks_and_exports(self):
        result = run_pipeline(SAMPLE_CSV, "orders.csv")

        self.assertEqual(result.profile.row_count, 12)
        self.assertEqual(result.profile.numeric_columns, ["amount"])
        self.assertEqual(result.profile.missing_by_column["status"], 1)
        self.assertEqual(result.profile.duplicate_rows, 1)
        self.assertTrue(any(issue.code == "missing_values" for issue in result.issues))
        self.assertTrue(any(issue.code == "duplicate_rows" for issue in result.issues))
        self.assertTrue(any(anomaly.column == "amount" for anomaly in result.anomalies))
        self.assertIn("date,category,amount,status", result.cleaned_csv)
        self.assertIn("SignalSweep report", result.report_markdown)
        self.assertEqual(result.workflow_status, "needs_review")
        self.assertEqual(result.actions[-1].action, "request_human_review")
        self.assertEqual(result.actions[-1].decision, "pause")
        self.assertTrue(result.actions[-1].requires_human_review)
        self.assertEqual([event.sequence for event in result.events], list(range(1, 10)))
        self.assertEqual(result.events[-1].status, "paused")

    def test_clean_dataset_is_marked_ready(self):
        result = run_pipeline(CLEAN_CSV, "clean.csv")

        self.assertEqual(result.workflow_status, "ready")
        self.assertEqual(result.actions[-1].action, "mark_dataset_ready")
        self.assertEqual(result.actions[-1].decision, "complete")
        self.assertEqual(result.events[-1].status, "completed")

    def test_empty_upload_is_rejected(self):
        with self.assertRaises(ValueError):
            run_pipeline("", "empty.csv")

    def test_event_service_returns_traceable_run(self):
        response = run_request(
            {
                "event_id": "evt-123",
                "dataset_name": "orders.csv",
                "csv_text": CLEAN_CSV,
            }
        )

        self.assertEqual(response["event_id"], "evt-123")
        self.assertEqual(response["dataset_name"], "orders.csv")
        self.assertEqual(response["workflow_status"], "ready")
        self.assertEqual(response["events"][0]["step"], "trigger")
        self.assertEqual(get_job_request("evt-123")["event_id"], "evt-123")

    def test_job_query_rejects_unknown_id(self):
        with self.assertRaisesRegex(KeyError, "No stored run"):
            get_job_request("not-found-001")

    def test_event_service_validates_payload(self):
        with self.assertRaisesRegex(ValueError, "csv_text"):
            run_request({"dataset_name": "missing.csv"})
        with self.assertRaisesRegex(ValueError, "event_id"):
            run_request({"csv_text": CLEAN_CSV, "event_id": ""})

    def test_event_id_is_idempotent_and_rejects_conflicting_input(self):
        payload = {
            "event_id": "idempotency-demo-001",
            "dataset_name": "clean.csv",
            "csv_text": CLEAN_CSV,
        }

        first = run_request(payload)
        replay = run_request(dict(payload))

        self.assertEqual(replay, first)
        with self.assertRaisesRegex(ValueError, "different request"):
            run_request({**payload, "csv_text": SAMPLE_CSV})

    def test_human_review_resumes_a_paused_job(self):
        event_id = "review-demo-001"
        run_request(
            {
                "event_id": event_id,
                "dataset_name": "orders.csv",
                "csv_text": SAMPLE_CSV,
            }
        )

        reviewed = review_request(
            {
                "event_id": event_id,
                "decision": "approve_normalized_copy",
                "note": "已检查异常金额，批准下载规范化副本，原始数据保留不变。",
                "approved_actions": ["remove_exact_duplicates"],
            }
        )

        self.assertEqual(reviewed["workflow_status"], "approved")
        self.assertEqual(reviewed["review"]["decision"], "approve_normalized_copy")
        self.assertEqual(reviewed["review"]["approved_actions"], ["remove_exact_duplicates"])
        self.assertEqual(reviewed["profile"]["duplicate_rows"], 0)
        self.assertEqual(reviewed["cleaned_csv"].count("2026-08-11,software,125,paid"), 1)
        self.assertIn("Workflow status: **approved**", reviewed["report_markdown"])
        self.assertIn("apply_approved_actions", [event["step"] for event in reviewed["events"]])
        self.assertEqual(reviewed["events"][-1]["step"], "human_review")
        self.assertEqual(reviewed["events"][-1]["status"], "completed")

        stored_record = service_module._JOB_STORE.get(event_id)
        self.assertIsNotNone(stored_record)
        self.assertNotIn("input", stored_record)
        self.assertTrue(stored_record["input_fingerprint"])
        self.assertEqual(run_request({
            "event_id": event_id,
            "dataset_name": "orders.csv",
            "csv_text": SAMPLE_CSV,
        }), reviewed)

        with self.assertRaisesRegex(ValueError, "not waiting"):
            review_request(
                {
                    "event_id": event_id,
                    "decision": "reject_run",
                    "note": "重复审核不应被接受。",
                }
            )

    def test_review_requires_an_existing_job(self):
        with self.assertRaisesRegex(KeyError, "No stored run"):
            review_request(
                {
                    "event_id": "missing-job",
                    "decision": "reject_run",
                    "note": "找不到任务。",
                }
            )

    def test_review_rejects_unknown_or_conflicting_actions(self):
        event_id = "review-validation-001"
        run_request({"event_id": event_id, "csv_text": SAMPLE_CSV})

        with self.assertRaisesRegex(ValueError, "Unsupported approved action"):
            review_request(
                {
                    "event_id": event_id,
                    "decision": "approve_normalized_copy",
                    "note": "测试未知动作。",
                    "approved_actions": ["fill_missing_values"],
                }
            )

        with self.assertRaisesRegex(ValueError, "cannot include"):
            review_request(
                {
                    "event_id": event_id,
                    "decision": "reject_run",
                    "note": "拒绝这次运行。",
                    "approved_actions": ["remove_exact_duplicates"],
                }
            )

    def test_health_payload_is_stable(self):
        self.assertEqual(
            health_payload(),
            {"status": "ok", "service": "signalsweep", "version": "0.3.0"},
        )


if __name__ == "__main__":
    unittest.main()
