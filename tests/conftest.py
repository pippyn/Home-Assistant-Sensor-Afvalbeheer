import sys
from pathlib import Path
from unittest.mock import MagicMock
from types import ModuleType
import importlib.abc
import importlib.machinery

# Add the workspace root to sys.path so custom_components can be imported
workspace_root = Path(__file__).parent.parent
sys.path.insert(0, str(workspace_root))

# Custom import hook for homeassistant modules
class MockHomeAssistantFinder(importlib.abc.MetaPathFinder):
    """Finder that provides mock modules for any homeassistant.* import."""
    
    def find_spec(self, fullname, path, target=None):
        if fullname.startswith('homeassistant'):
            # Only handle if not already in sys.modules
            if fullname not in sys.modules:
                loader = MockHomeAssistantLoader()
                return importlib.machinery.ModuleSpec(fullname, loader, is_package=True)
        return None

class MockHomeAssistantLoader(importlib.abc.Loader):
    """Loader that creates mock modules."""
    
    def create_module(self, spec):
        module = ModuleType(spec.name)
        module.__path__ = []
        module.__loader__ = self
        module.__package__ = spec.name
        
        # Make attribute access return MagicMock
        def getattr_override(name):
            if name.startswith('_'):
                return object.__getattribute__(module, name)
            # Return a MagicMock that can also be a submodule
            return MagicMock()
        
        module.__getattr__ = getattr_override
        return module
    
    def exec_module(self, module):
        pass

# Register the finder
sys.meta_path.insert(0, MockHomeAssistantFinder())

# Pre-create some key modules explicitly for better reliability
class MockModule(ModuleType):
    """A module that returns MagicMock for any attribute access."""
    def __getattr__(self, name):
        if name.startswith('_'):
            return super().__getattribute__(name)
        return MagicMock()

def create_mock_hierarchy(name):
    """Create a mock module hierarchy."""
    module = MockModule(name)
    module.__path__ = []
    module.__loader__ = None
    module.__package__ = name
    return module

# Pre-populate common modules
sys.modules['homeassistant'] = create_mock_hierarchy('homeassistant')
sys.modules['homeassistant.const'] = create_mock_hierarchy('homeassistant.const')
sys.modules['homeassistant.core'] = create_mock_hierarchy('homeassistant.core')
sys.modules['homeassistant.helpers'] = create_mock_hierarchy('homeassistant.helpers')
sys.modules['homeassistant.helpers.aiohttp_client'] = create_mock_hierarchy('homeassistant.helpers.aiohttp_client')
sys.modules['homeassistant.helpers.storage'] = create_mock_hierarchy('homeassistant.helpers.storage')
sys.modules['homeassistant.helpers.event'] = create_mock_hierarchy('homeassistant.helpers.event')

# Explicitly set useful mocks
sys.modules['homeassistant.helpers.aiohttp_client'].async_get_clientsession = MagicMock()
sys.modules['homeassistant.helpers.storage'].Store = MagicMock()
sys.modules['homeassistant.const'].Platform = MagicMock()
