"""Enforce import boundaries so any service folder can be deleted safely.

Rules:
1. libs/aibase never imports a *_service package.
2. A service never imports another service.
3. aibase subpackages only import from layers below them.
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAYERS = [  # top -> bottom; a layer may import only from layers below it
    {"api"},
    {"guardrails", "evals", "prompts"},
    {"providers"},
    {"observability", "audit"},
    {"phi"},
    {"core"},
]
LAYER_OF = {pkg: i for i, layer in enumerate(LAYERS) for pkg in layer}
SAME_LAYER_ALLOWED = False


def imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.append(node.module)
    return modules


def check_lib_file(path: Path, errors: list[str]) -> None:
    rel = path.relative_to(ROOT / "libs" / "aibase")
    owner = rel.parts[0] if len(rel.parts) > 1 else None
    for module in imported_modules(path):
        top = module.split(".")[0]
        if top.endswith("_service"):
            errors.append(f"{path}: lib imports service '{module}'")
        parts = module.split(".")
        if parts[0] != "aibase" or len(parts) < 2 or owner not in LAYER_OF:
            continue
        target = parts[1]
        if target not in LAYER_OF or target == owner:
            continue
        if LAYER_OF[target] <= LAYER_OF[owner]:
            errors.append(f"{path}: layer '{owner}' must not import '{target}'")


def check_service_file(path: Path, own_package: str, errors: list[str]) -> None:
    for module in imported_modules(path):
        top = module.split(".")[0]
        if top.endswith("_service") and top != own_package:
            errors.append(f"{path}: service imports other service '{top}'")


def main() -> int:
    errors: list[str] = []
    for path in (ROOT / "libs" / "aibase").rglob("*.py"):
        if "testing" in path.parts or "tests" in path.parts:
            continue
        check_lib_file(path, errors)
    for src in ROOT.glob("services/*/src/*_service"):
        for path in src.rglob("*.py"):
            check_service_file(path, src.name, errors)
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
