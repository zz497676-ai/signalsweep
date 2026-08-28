import unittest

from signalsweep.agent import root_agent


class AgentIntegrationTests(unittest.TestCase):
    @unittest.skipIf(root_agent is None, "google-adk is not installed")
    def test_root_agent_registers_taskmaster_tools(self):
        self.assertEqual(root_agent.name, "signalsweep_agent")
        tool_names = [getattr(tool, "__name__", type(tool).__name__) for tool in root_agent.tools]
        self.assertEqual(
            tool_names,
            ["profile_csv_tool", "taskmaster_workflow_tool"],
        )


if __name__ == "__main__":
    unittest.main()
