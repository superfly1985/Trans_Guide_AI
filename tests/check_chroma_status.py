# -*- coding: utf-8 -*-
"""检查 ChromaDB 同步状态"""
import sys, os
sys.path.insert(0, "/root/Trans_Guide_AI")
os.chdir("/root/Trans_Guide_AI")

import chromadb

print("=== ChromaDB 状态检查 ===")
client = chromadb.PersistentClient(path="./data/chroma_db")
collections = client.list_collections()
print(f"Collections: {[c.name for c in collections]}")

for c in collections:
    print(f"  Collection '{c.name}': count={c.count()}")

print("\n=== SQLite 状态 ===")
import sqlite3
conn = sqlite3.connect("./data/tm.db")
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM translation_memory")
count = cursor.fetchone()[0]
print(f"SQLite translation_memory count: {count}")
conn.close()

print("\n=== 模型文件 ===")
model_path = "/root/.cache/chroma/onnx_models/all-MiniLM-L6-v2"
if os.path.exists(model_path):
    files = os.listdir(model_path)
    print(f"Model files: {files}")
else:
    print("Model not downloaded yet")
