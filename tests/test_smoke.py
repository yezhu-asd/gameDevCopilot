import unittest

from core import config
from core.pipeline import cleanup, make_temp_output, run_pipeline


class TestSmokeEndToEnd(unittest.TestCase):
    """Verify the generate->verify->fix loop against a real LLM and real Godot.

    Requires LLM_API_KEY + LLM_BASE_URL to be configured. Skipped otherwise.
    """

    @classmethod
    def setUpClass(cls):
        cls.out_root = make_temp_output()

    @classmethod
    def tearDownClass(cls):
        cleanup(cls.out_root)

    def test_smoke(self):
        if not config.LLM_API_KEY:
            self.skipTest("LLM_API_KEY 未配置")
        spec = "做一个最小的 2D 游戏：一个可以 WASD 移动的方块，一个静态墙，碰到墙不会穿过。"
        result = run_pipeline(spec, self.out_root, max_rounds=3)
        self.assertTrue(result.success, f"未通过，最近错误: {result.last_errors}")
        self.assertTrue(result.final_dir.exists())


if __name__ == "__main__":
    unittest.main()
