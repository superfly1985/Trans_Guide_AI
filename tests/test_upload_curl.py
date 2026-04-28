# -*- coding: utf-8 -*-
"""测试上传功能"""

import requests
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_upload():
    url = "http://127.0.0.1:5555/api/import/upload"
    file_path = "tests/test_doc/3122059历史翻译.DOC"
    
    print(f"测试文件: {file_path}")
    print(f"URL: {url}")
    
    with open(file_path, 'rb') as f:
        files = {'file': ('3122059历史翻译.DOC', f)}
        print("发送请求...")
        try:
            response = requests.post(url, files=files, timeout=120)
            print(f"状态码: {response.status_code}")
            print(f"响应内容: {response.text[:2000]}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"\n=== 结果 ===")
                print(f"Success: {data.get('success')}")
                print(f"Total terms: {data.get('total_terms')}")
                print(f"Total pairs: {data.get('total_pairs')}")
                print(f"LLM used: {data.get('llm_used')}")
        except Exception as e:
            print(f"请求失败: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    test_upload()
