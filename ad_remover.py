"""顶层启动器：允许直接 `python ad_remover.py <command>` 运行。"""
import sys
from ad_remover import main

if __name__ == "__main__":
    raise SystemExit(main())
