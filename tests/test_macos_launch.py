from types import SimpleNamespace

from synthetic_human.desktop import MacDesktop
from synthetic_human.models import Primitive


async def test_launch_explicitly_activates_target_before_runtime_focus_check(monkeypatch):
    # Native application stubs; no real app is launched by this unit test.
    activations = []
    application = SimpleNamespace(
        localizedName=lambda: "Google Chrome",
        activateWithOptions_=lambda options: activations.append(options) or True,
    )
    workspace = SimpleNamespace(runningApplications=lambda: [application])
    backend = object.__new__(MacDesktop)
    backend.pg = SimpleNamespace(failSafeCheck=lambda: None)
    backend.AppKit = SimpleNamespace(
        NSWorkspace=SimpleNamespace(sharedWorkspace=lambda: workspace),
        NSApplicationActivateAllWindows=1,
    )

    async def communicate():
        return (None, b"")

    async def launch(*args, **kwargs):
        assert args == ("open", "-a", "Google Chrome")
        return SimpleNamespace(returncode=0, communicate=communicate)

    monkeypatch.setattr("synthetic_human.desktop.asyncio.create_subprocess_exec", launch)
    await backend.emit(Primitive(kind="launch", value=["Google Chrome"]))
    assert activations == [1]
