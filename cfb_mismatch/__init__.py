"""Compatibility package that exposes the implementation living under src/."""
from __future__ import annotations

from pathlib import Path

# Resolve the location of the actual implementation package that lives under ``src``
# so that the project can be used without installing it as a distribution.
_pkg_root = Path(__file__).resolve().parent.parent / "src" / "cfb_mismatch"
if not _pkg_root.exists():
    raise ModuleNotFoundError(
        "The implementation package could not be located. Expected to find it at "
        f"{_pkg_root}."
    )

# Ensure Python will search for submodules (e.g. ``cfb_mismatch.main``) in the
# directory that contains the actual sources.
__path__ = [str(_pkg_root)]

# Execute the original ``__init__`` so that any public symbols defined there are
# available directly from this compatibility package.
_init_file = _pkg_root / "__init__.py"
if _init_file.exists():
    compiled = compile(_init_file.read_text(encoding="utf-8"), str(_init_file), "exec")
    exec(compiled, globals())
