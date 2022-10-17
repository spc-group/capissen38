import pytest

from haven.instrument.instrument_registry import registry
from simulated_ioc import ioc_motor


def test_create_motors(ioc_motor):
    from haven.instrument import motor

    # Were the motors import correctly
    motors = registry.findall(label="motor")
    assert len(motors) == 3
    assert motors[0].name == "SLT V Upper"
