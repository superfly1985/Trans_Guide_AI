# -*- coding: utf-8 -*-
"""测试 app.py 导入"""
import sys
sys.path.insert(0, ".")

try:
    print("Importing app...")
    from web.app import app
    print("App imported OK")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
