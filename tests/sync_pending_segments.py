# -*- coding: utf-8 -*-
"""手动同步 SQLite 句段到 ChromaDB"""
import sys, os
sys.path.insert(0, "/root/Trans_Guide_AI")
os.chdir("/root/Trans_Guide_AI")

from modules.tm_db import TMDatabase

print("=== 开始同步句段到 ChromaDB ===")
tm = TMDatabase("./data/tm.db", "./data/chroma_db")

# 获取所有句段 ID
import sqlite3
conn = sqlite3.connect("./data/tm.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("SELECT id FROM translation_memory ORDER BY id")
ids = [row["id"] for row in cursor.fetchall()]
conn.close()

print(f"SQLite 中共有 {len(ids)} 个句段需要同步")

if ids:
    synced = tm.sync_to_chroma(ids)
    print(f"同步完成: {synced}/{len(ids)} 个句段已同步到 ChromaDB")
else:
    print("没有句段需要同步")

# 验证
import chromadb
client = chromadb.PersistentClient(path="./data/chroma_db")
coll = client.get_collection("translation_memory")
print(f"ChromaDB translation_memory count: {coll.count()}")
