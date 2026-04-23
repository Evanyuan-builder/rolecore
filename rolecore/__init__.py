import os

from .storage.role_store import RoleStore
from .storage.registry_store import RegistryStore
from .core.role_manager import RoleManager
from .core.search_engine import SearchEngine
from .core.fusion_search import FusionSearchEngine
from .core.assembler import Assembler

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ROLES_DIR = os.path.join(_BASE_DIR, "roles")
_REGISTRY_PATH = os.path.join(_BASE_DIR, "registry", "registry.json")


def create_default_engine():
    role_store = RoleStore(_ROLES_DIR)
    registry_store = RegistryStore(_REGISTRY_PATH)
    role_manager = RoleManager(role_store, registry_store)
    search_engine = SearchEngine(registry_store)
    assembler = Assembler(role_manager)
    return role_manager, search_engine, assembler


def create_fusion_engine():
    registry_store = RegistryStore(_REGISTRY_PATH)
    return FusionSearchEngine(registry_store)
