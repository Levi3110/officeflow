import pytest

from synthetic_human.authority import AuthorityManager
from synthetic_human.desktop import SimulationDesktop
from synthetic_human.models import Settings
from synthetic_human.runtime import Runtime
from synthetic_human.store import Store


@pytest.fixture
def rig(tmp_path):
    settings = Settings()
    store = Store(tmp_path / "state.sqlite")
    authority = AuthorityManager(store, settings)
    backend = SimulationDesktop(settings)
    runtime = Runtime(store, authority, backend, settings, tmp_path)
    yield runtime
    store.close()
