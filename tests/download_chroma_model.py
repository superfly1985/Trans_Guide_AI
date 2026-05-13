# -*- coding: utf-8 -*-
"""触发 ChromaDB embedding 模型下载"""
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

import chromadb

print("Starting ChromaDB model download...")
client = chromadb.PersistentClient(path="./data/chroma_db")
coll = client.get_or_create_collection("download_trigger")
coll.add(ids=["1"], documents=["trigger download"])
print("Download complete!")
