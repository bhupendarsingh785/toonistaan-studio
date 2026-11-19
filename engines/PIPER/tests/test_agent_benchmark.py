import unittest
from agent_benchmark import fixture_self_test
class AgentBenchmarkTests(unittest.TestCase):
    def test_benchmark_fixture(self):
        result=fixture_self_test()
        self.assertTrue(result["passed"])
        self.assertEqual(result["score"],100.0)
if __name__=="__main__": unittest.main()
