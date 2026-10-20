"""跨目录定位项目根并调用数据需求引擎。

用法::

    py SKILL/data-requirement/scripts/run_engine.py generate -i doc/input/research_brief.md
    py SKILL/data-requirement/scripts/run_engine.py validate
    py SKILL/data-requirement/scripts/run_engine.py sample --confidence 0.95 --error 0.05

项目根按以下顺序查找：
1. ``--project-root`` 参数；
2. 环境变量 ``DATA_REQUIREMENT_PROJECT_ROOT``；
3. 从当前工作目录向上查找；
4. 从本脚本所在目录向上查找。

项目根的判定标准：同时存在 ``engine/cli.py`` 与 ``doc/input/``。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _is_project_root(path: Path) -> bool:
    return (path / "engine" / "cli.py").is_file() and (path / "doc" / "input").is_dir()


def _walk_up(start: Path) -> Path | None:
    try:
        current = start.resolve()
    except OSError:
        return None
    for candidate in [current, *current.parents]:
        if _is_project_root(candidate):
            return candidate
    return None


def find_project_root(explicit: str | None = None) -> Path | None:
    if explicit:
        p = Path(explicit).expanduser()
        if p.is_dir() and _is_project_root(p):
            return p.resolve()
        return None

    env = os.environ.get("DATA_REQUIREMENT_PROJECT_ROOT")
    if env:
        p = Path(env).expanduser()
        if p.is_dir() and _is_project_root(p):
            return p.resolve()

    found = _walk_up(Path.cwd())
    if found:
        return found

    return _walk_up(Path(__file__).resolve().parent)


def main(argv: list[str] | None = None) -> int:
    wrapper = argparse.ArgumentParser(add_help=False)
    wrapper.add_argument("--project-root", default=None, help="项目根目录（包含 engine/ 与 doc/）")
    known, rest = wrapper.parse_known_args(argv)

    root = find_project_root(known.project_root)
    if root is None:
        print(
            "找不到项目根目录。请确认当前目录在项目内，或使用：\n"
            "  py <skill>/scripts/run_engine.py --project-root D:/path/to/project generate ...\n"
            "也可设置环境变量 DATA_REQUIREMENT_PROJECT_ROOT。",
            file=sys.stderr,
        )
        return 2

    os.chdir(root)
    sys.path.insert(0, str(root))
    from engine.cli import main as engine_main

    return engine_main(rest)


if __name__ == "__main__":
    raise SystemExit(main())
