import ast
from pathlib import Path


FORBIDDEN_IMPORTS = {
    "PySide6",
    "fastapi",
    "mlx",
    "sounddevice",
    "stepaudio",
    "stepfun",
    "viaim",
}


def test_core_imports_no_forbidden_packages() -> None:
    root = Path(__file__).resolve().parents[2] / "src/meantbyme/core"
    violations = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [node.module.split(".")[0]]
            else:
                continue
            for package in imported:
                if package in FORBIDDEN_IMPORTS:
                    violations.append(f"{path}:{node.lineno}:{package}")
    assert violations == []
