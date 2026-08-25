import json
import unittest

from app.ui.server import SERAUIServer


class TestPhase5DWorkflowGraph(unittest.TestCase):
    def setUp(self):
        self.server = SERAUIServer(port=8797)

    def test_01_structured_workflow_graph_schema(self):
        graph = self.server._get_structured_workflow_graph()
        self.assertEqual(graph["version"], 1)
        self.assertIn("nodes", graph)
        self.assertIn("edges", graph)
        self.assertIn("roles", graph)
        self.assertIn("layout", graph)
        self.assertGreater(len(graph["nodes"]), 0)

        # Check required fields on each node
        for node in graph["nodes"]:
            self.assertIn("id", node)
            self.assertIn("label", node)
            self.assertIn("kind", node)
            self.assertIn("status", node)
            self.assertIn("x", node)
            self.assertIn("y", node)
            self.assertIn("width", node)
            self.assertIn("height", node)

        # Check required fields on each edge
        for edge in graph["edges"]:
            self.assertIn("id", edge)
            self.assertIn("from", edge)
            self.assertIn("to", edge)
            self.assertIn("kind", edge)


if __name__ == "__main__":
    unittest.main()
