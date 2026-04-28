# -*- coding: utf-8 -*-
"""
测试文件上传和术语提取
"""

import sys
import os
import io

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.app import app

def test_file_upload():
    """测试文件上传"""
    with app.test_client() as client:
        # 读取测试文件
        test_file_path = 'tests/test_doc/3122059历史翻译.DOC'
        if not os.path.exists(test_file_path):
            print(f"错误: 测试文件不存在: {test_file_path}")
            return
            
        with open(test_file_path, 'rb') as f:
            file_content = f.read()
        
        print(f"文件大小: {len(file_content)} 字节")
        print("发送上传请求...")
        
        # 创建multipart/form-data请求
        resp = client.post(
            '/api/import/upload',
            data={'file': (io.BytesIO(file_content), '3122059历史翻译.DOC')},
            content_type='multipart/form-data'
        )
        
        print(f"Status: {resp.status_code}")
        result = resp.get_json()
        
        print(f"Success: {result.get('success')}")
        print(f"Total terms: {result.get('total_terms')}")
        print(f"Total pairs: {result.get('total_pairs')}")
        print(f"Message: {result.get('message')}")
        print(f"LLM used: {result.get('llm_used')}")
        
        if result.get('potential_terms'):
            print(f"\n提取的术语 (共{len(result.get('potential_terms', []))}个):")
            for i, term in enumerate(result.get('potential_terms', [])[:15], 1):
                print(f"  {i}. {term.get('english')} -> {term.get('chinese')} ({term.get('category', '未分类')})")
        else:
            print("\n没有提取到术语")
        
        return result

if __name__ == "__main__":
    test_file_upload()
