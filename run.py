#!/usr/bin/env python
"""專案啟動器。

在 Windows embeddable 版 Python (使用 ._pth 隔離模式) 下，PYTHONPATH 與 cwd
不會自動加入 sys.path，因此用這個位於專案根目錄的啟動器把根目錄補上，
再轉交給 crawler.main。

用法與 `python -m crawler.main` 完全相同，例如:
    python run.py
    python run.py --watch --interval 60 --keywords 台積電 AI
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crawler.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
