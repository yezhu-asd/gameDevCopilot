from core import config
from core.verifier import verify_project


def test_smoke_example_passes():
    """The known-good playground project must verify clean."""
    result = verify_project(config.SMOKE_EXAMPLE)
    assert result.passed, f"已知良好项目居然报错: {result.errors}"
