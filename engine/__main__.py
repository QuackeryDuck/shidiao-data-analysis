"""允许使用 ``python -m engine`` 运行命令行。"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
