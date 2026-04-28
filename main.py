# -*- coding: utf-8 -*-
"""
作业指导书智能翻译系统入口文件
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.cli import main

if __name__ == "__main__":
    main()
