# -*- coding: utf-8 -*-
"""测试 ChromaDB 使用国内镜像下载 embedding 模型"""
import os

# 设置国内镜像 - 必须在导入 chromadb 之前设置
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

print(f'HF_ENDPOINT: {os.environ.get("HF_ENDPOINT", "not set")}')

try:
    import chromadb
    print('ChromaDB imported')
    
    # 创建临时客户端
    client = chromadb.Client()
    print('ChromaDB client created')
    
    # 创建 collection - 这会触发 embedding 模型下载
    collection = client.get_or_create_collection(name="test_mirror")
    print(f'Collection created: {collection}')
    
    # 添加文档 - 这会触发模型下载和编码
    collection.add(
        ids=["1", "2"],
        documents=["hello world", "你好世界"]
    )
    print('Documents added successfully!')
    
    # 查询测试
    results = collection.query(query_texts=["hello"], n_results=1)
    print(f'Query results: {results}')
    print('\nSuccess! Mirror works with ChromaDB!')
    
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
