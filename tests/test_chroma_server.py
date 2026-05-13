# -*- coding: utf-8 -*-
"""在服务器上测试 ChromaDB + HF 镜像"""
import os
import sys

# 设置国内镜像
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

print(f'Python: {sys.version}')
print(f'HF_ENDPOINT: {os.environ.get("HF_ENDPOINT", "not set")}')

try:
    import chromadb
    print('ChromaDB imported')
    
    # 使用持久化客户端（和实际代码一致）
    client = chromadb.PersistentClient(path='/tmp/test_chroma')
    print('ChromaDB persistent client created')
    
    collection = client.get_or_create_collection(name="test_mirror")
    print(f'Collection created')
    
    # 添加文档
    collection.add(
        ids=["1", "2"],
        documents=["hello world", "你好世界"]
    )
    print('Documents added!')
    
    # 查询
    results = collection.query(query_texts=["hello"], n_results=1)
    print(f'Query success! Distance: {results["distances"][0][0]:.4f}')
    print('\nSUCCESS! Mirror works on server!')
    
except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()
