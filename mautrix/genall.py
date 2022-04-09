# This script generates the __all__ arrays for types/__init__.py and errors/__init__.py
# to avoid having to manually add both the import and the __all__ entry.
# See https://github.com/mautrix/python/issues/90 for why __all__ is needed at all.
from pathlib import Path
import ast

import black

root_module = Path(__file__).parent

black_cfg = black.parse_pyproject_toml(str(root_module.parent / "pyproject.toml"))
black_mode = black.Mode(
    target_versions={black.TargetVersion[ver.upper()] for ver in black_cfg["target_version"]},
    line_length=black_cfg["line_length"],
)


def add_imports_to_all(dir: str) -> None:
    init_file = root_module / dir / "__init__.py"
    with open(init_file) as f:
        init_ast = ast.parse(f.read(), filename=f"mautrix/{dir}/__init__.py")

    imports: list[str] = []
    all_node: ast.List | None = None

    for node in ast.iter_child_nodes(init_ast):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports += (name.name for name in node.names)
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.List):
            target = node.targets[0]
            if len(node.targets) == 1 and isinstance(target, ast.Name) and target.id == "__all__":
                all_node = node.value

    all_node.elts = [ast.Constant(name) for name in imports]

    with open(init_file, "w") as f:
        f.write(black.format_str(ast.unparse(init_ast), mode=black_mode))


add_imports_to_all("types")
add_imports_to_all("errors")
