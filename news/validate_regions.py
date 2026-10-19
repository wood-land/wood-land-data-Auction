"""Offline structural validation for numbered regional Site modules."""
from __future__ import annotations
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def main() -> int:
    errors = []
    modules = sorted((ROOT / "regions").glob("12_*.py"))
    for path in modules:
        module = importlib.import_module(f"regions.{path.stem}")
        name = getattr(module, "REGION_NAME", None)
        sites = getattr(module, "SITES", None)
        if not isinstance(name, str) or not isinstance(sites, list):
            errors.append(f"{path.name}: invalid REGION_NAME or SITES")
            continue
        site_names = [getattr(site, "name", None) for site in sites]
        if any(not isinstance(value, str) or not value for value in site_names):
            errors.append(f"{path.name}: missing Site name")
        if len(set(site_names)) != len(site_names):
            errors.append(f"{path.name}: duplicate Site name")
        if any(not site.enabled and not site.disabled_reason for site in sites):
            errors.append(f"{path.name}: disabled Site missing reason")
        print(f"{path.name}: {len(sites)} Site(s), structural check OK")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"All {len(modules)} numbered region modules passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
