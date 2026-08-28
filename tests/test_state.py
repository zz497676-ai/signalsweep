import tempfile
import unittest
from pathlib import Path

from signalsweep.state import InMemoryJobStore, SQLiteJobStore


class StateStoreTests(unittest.TestCase):
    def test_memory_store_returns_isolated_records(self):
        store = InMemoryJobStore()
        record = {"response": {"workflow_status": "needs_review"}}
        store.put("evt-memory", record)
        record["response"]["workflow_status"] = "mutated-outside"

        self.assertEqual(
            store.get("evt-memory"),
            {"response": {"workflow_status": "needs_review"}},
        )

    def test_sqlite_store_survives_a_new_store_instance(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "jobs.sqlite3"
            first_store = SQLiteJobStore(path)
            first_store.put("evt-sqlite", {"response": {"workflow_status": "paused"}})

            second_store = SQLiteJobStore(path)
            self.assertEqual(
                second_store.get("evt-sqlite"),
                {"response": {"workflow_status": "paused"}},
            )

            second_store.delete("evt-sqlite")
            self.assertIsNone(second_store.get("evt-sqlite"))


if __name__ == "__main__":
    unittest.main()
