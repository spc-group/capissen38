import pytest
from bluesky import RunEngine


class RunEngineStub(RunEngine):
    def __repr__(self):
        return "<run_engine.RunEngineStub>"


@pytest.fixture()
def RE(event_loop):
    return RunEngineStub(call_returns_result=True)
