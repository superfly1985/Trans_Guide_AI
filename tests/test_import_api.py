# -*- coding: utf-8 -*-
"""测试导入API"""
import sys
sys.path.insert(0, ".")

from modules.tm_db import TMDatabase

print("Test 1: TMDatabase init...")
tm = TMDatabase("./data/tm.db", "./data/chroma_db")
print("OK")

print("Test 2: add_segments_batch_fast...")
stats, ids = tm.add_segments_batch_fast([("hello","你好"),("world","世界")], "test")
print(f"Stats: {stats}, IDs: {ids}")

print("Test 3: sync_to_chroma...")
if ids:
    synced = tm.sync_to_chroma(ids)
    print(f"Synced: {synced}")
else:
    print("No IDs to sync")

print("All tests passed!")
