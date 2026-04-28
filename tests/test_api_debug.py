# -*- coding: utf-8 -*-
"""
调试 API 上传功能
"""

import sys
import os
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.app import app

def test_upload():
    with app.test_client() as client:
        # 读取测试文件
        test_file_path = 'tests/test_doc/3122059历史翻译.DOC'
        with open(test_file_path, 'rb') as f:
            file_content = f.read()
        
        print(f"文件大小: {len(file_content)} 字节")
        print("发送上传请求...")
        
        resp = client.post(
            '/api/import/upload',
            data={'file': (io.BytesIO(file_content), '3122059历史翻译.DOC')},
            content_type='multipart/form-data'
        )
        
        print(f"Status: {resp.status_code}")
        result = resp.get_json()
        
        print(f"\n=== 结果 ===")
        print(f"Success: {result.get('success')}")
        print(f"Total terms: {result.get('total_terms')}")
        print(f"Total pairs: {result.get('total_pairs')}")
        print(f"LLM used: {result.get('llm_used')}")
        print(f"Message: {result.get('message')}")
        
        if result.get('potential_terms'):
            print(f"\n提取的术语:")
            for i, term in enumerate(result.get('potential_terms', [])[:10], 1):
                print(f"  {i}. {term.get('english')} -> {term.get('chinese')}")
        else:
            print("\n没有提取到术语")
            print("这是 Web API 的问题！")

if __name__ == "__main__":
    test_upload()
