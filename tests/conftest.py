import pytest

from generator.__main__ import generate


@pytest.fixture(scope="session")
def seed1(tmp_path_factory):
    """Seed 1, N=500, generated once per test session."""
    out = tmp_path_factory.mktemp("gen") / "seed-1"
    generate(1, 500, out)
    return out
