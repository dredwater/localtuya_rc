"""Tests for LocalTuyaIR protocol version handling."""

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "custom_components" / "localtuya_rc"

# Minimal Home Assistant stubs used by localtuya_rc config_flow imports.
homeassistant = types.ModuleType("homeassistant")
homeassistant.config_entries = types.ModuleType("homeassistant.config_entries")

class ConfigFlow:
    def __init_subclass__(cls, *args, **kwargs):
        return super().__init_subclass__()

class OptionsFlow:
    pass

homeassistant.config_entries.ConfigFlow = ConfigFlow
homeassistant.config_entries.OptionsFlow = OptionsFlow
homeassistant.core = types.ModuleType("homeassistant.core")

homeassistant.core.callback = lambda f: f
homeassistant.helpers = types.ModuleType("homeassistant.helpers")
homeassistant.helpers.config_validation = types.ModuleType("homeassistant.helpers.config_validation")
homeassistant.helpers.config_validation.string = str
homeassistant.helpers.config_validation.boolean = bool
homeassistant.const = types.ModuleType("homeassistant.const")
for name in (
    "CONF_NAME",
    "CONF_HOST",
    "CONF_DEVICE_ID",
    "CONF_REGION",
    "CONF_CLIENT_ID",
    "CONF_CLIENT_SECRET",
):
    setattr(homeassistant.const, name, name.lower())

sys.modules["homeassistant"] = homeassistant
sys.modules["homeassistant.config_entries"] = homeassistant.config_entries
sys.modules["homeassistant.core"] = homeassistant.core
sys.modules["homeassistant.helpers"] = homeassistant.helpers
sys.modules["homeassistant.helpers.config_validation"] = homeassistant.helpers.config_validation
sys.modules["homeassistant.const"] = homeassistant.const

# Load the localtuya_rc package modules without requiring the full HA runtime.
package = types.ModuleType("localtuya_rc")
package.__path__ = [str(PACKAGE_DIR)]
sys.modules["localtuya_rc"] = package

spec = importlib.util.spec_from_file_location("localtuya_rc.const", PACKAGE_DIR / "const.py")
const = importlib.util.module_from_spec(spec)
sys.modules["localtuya_rc.const"] = const
spec.loader.exec_module(const)

spec = importlib.util.spec_from_file_location("localtuya_rc.config_flow", PACKAGE_DIR / "config_flow.py")
config_flow = importlib.util.module_from_spec(spec)
sys.modules["localtuya_rc.config_flow"] = config_flow
spec.loader.exec_module(config_flow)


def test_tuya_versions_prefers_35():
    assert const.TUYA_VERSIONS[0] == "3.5"


def test_test_connection_converts_protocol_35_to_float(monkeypatch):
    recorded = {}

    class FakeIRRemoteControlDevice:
        def __init__(self, *args, **kwargs):
            recorded["kwargs"] = kwargs
            self.control_type = kwargs.get("control_type", 0)

        def status(self):
            return {"success": True}

    monkeypatch.setattr(config_flow.Contrib, "IRRemoteControlDevice", FakeIRRemoteControlDevice)

    flow = config_flow.LocalTuyaIRConfigFlow()
    device, status = flow._test_connection(
        dev_id="test-device",
        address="192.0.2.1",
        local_key="0123456789abcdef",
        version="3.5",
    )

    assert isinstance(device, FakeIRRemoteControlDevice)
    assert recorded["kwargs"]["version"] == 3.5
    assert status == {"success": True}

def test_remote_runtime_prefers_control_type_2_for_v35():
    homeassistant.helpers.entity = types.ModuleType("homeassistant.helpers.entity")
    homeassistant.helpers.entity.DeviceInfo = lambda **kwargs: kwargs
    homeassistant.exceptions = types.ModuleType("homeassistant.exceptions")

    class HomeAssistantError(Exception):
        pass

    homeassistant.exceptions.HomeAssistantError = HomeAssistantError
    homeassistant.components = types.ModuleType("homeassistant.components")
    homeassistant.components.persistent_notification = types.ModuleType("homeassistant.components.persistent_notification")
    homeassistant.components.persistent_notification.async_create = lambda *args, **kwargs: None
    homeassistant.components.remote = types.ModuleType("homeassistant.components.remote")
    homeassistant.components.remote.ATTR_COMMAND_TYPE = "command_type"
    homeassistant.components.remote.ATTR_TIMEOUT = "timeout"
    homeassistant.components.remote.ATTR_ALTERNATIVE = "alternative"
    homeassistant.components.remote.ATTR_COMMAND = "command"
    homeassistant.components.remote.ATTR_DEVICE = "device"
    homeassistant.components.remote.ATTR_DELAY_SECS = "delay_secs"
    homeassistant.components.remote.ATTR_NUM_REPEATS = "num_repeats"
    homeassistant.components.remote.ATTR_HOLD_SECS = "hold_secs"

    class RemoteEntity:
        pass

    class RemoteEntityFeature:
        LEARN_COMMAND = 1
        DELETE_COMMAND = 2

    homeassistant.components.remote.RemoteEntity = RemoteEntity
    homeassistant.components.remote.RemoteEntityFeature = RemoteEntityFeature

    class _DummyPlatformSchema:
        def extend(self, *args, **kwargs):
            return self

    homeassistant.components.remote.PLATFORM_SCHEMA = _DummyPlatformSchema()
    homeassistant.helpers.storage = types.ModuleType("homeassistant.helpers.storage")

    class Store:
        def __init__(self, *args, **kwargs):
            pass

    homeassistant.helpers.storage.Store = Store

    sys.modules["homeassistant.helpers.entity"] = homeassistant.helpers.entity
    sys.modules["homeassistant.exceptions"] = homeassistant.exceptions
    sys.modules["homeassistant.components"] = homeassistant.components
    sys.modules["homeassistant.components.persistent_notification"] = homeassistant.components.persistent_notification
    sys.modules["homeassistant.components.remote"] = homeassistant.components.remote
    sys.modules["homeassistant.helpers.storage"] = homeassistant.helpers.storage

    spec = importlib.util.spec_from_file_location("localtuya_rc.remote", PACKAGE_DIR / "remote.py")
    remote = importlib.util.module_from_spec(spec)
    sys.modules["localtuya_rc.remote"] = remote
    spec.loader.exec_module(remote)

    assert remote.TuyaRC._control_type_candidates(0, "3.5") == [2, 1]
    assert remote.TuyaRC._control_type_candidates("Auto", "3.5") == [2, 1]
    assert remote.TuyaRC._control_type_candidates(2, "3.5") == [2]
