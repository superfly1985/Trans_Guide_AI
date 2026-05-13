# -*- coding: utf-8 -*-
"""测试 HuggingFace 国内镜像下载"""
import os

# 设置国内镜像
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

print(f'HF_ENDPOINT: {os.environ.get("HF_ENDPOINT", "not set")}')

try:
    from sentence_transformers import SentenceTransformer
    print('Testing HF mirror download...')
    
    # 尝试加载模型（如果不存在会自动下载）
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print(f'Model loaded: {model}')
    
    # 测试编码
    texts = ['hello world', '你好世界']
    embeddings = model.encode(texts)
    print(f'Embeddings shape: {embeddings.shape}')
    print('Success! Mirror works!')
    
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
