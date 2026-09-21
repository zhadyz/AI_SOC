"""Importable service namespaces while preserving existing deployment directories.

Use ``services.alert_triage`` (and analogous underscore names) in Python. Each
namespace points to the corresponding service directory without importing its
application or optional dependencies.
"""

from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType
import sys

_root = Path(__file__).parent
for _directory in sorted(_root.iterdir()):
    if _directory.is_dir() and "-" in _directory.name:
        _name = f"{__name__}.{_directory.name.replace('-', '_')}"
        _package = ModuleType(_name)
        _package.__path__ = [str(_directory)]
        _package.__package__ = _name
        _package.__spec__ = ModuleSpec(_name, loader=None, is_package=True)
        _package.__spec__.submodule_search_locations = _package.__path__
        sys.modules.setdefault(_name, _package)
        setattr(sys.modules[__name__], _directory.name.replace('-', '_'), sys.modules[_name])
