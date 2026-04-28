# -*- coding: utf-8 -*-
"""
测试 Web 导入 API
"""

import requests
import os

BASE_URL = "http://127.0.0.1:5555"
TEST_FILE = r"d:\01.AwesomeProject\52.Trans_Guide_AI\tests\test_doc\3122059历史翻译.DOC"


def test_import_api():
    """测试导入 API"""
    
    print("=" * 60)
    print("测试 Web 导入 API")
    print("=" * 60)
    
    if not os.path.exists(TEST_FILE):
        print(f"❌ 测试文件不存在: {TEST_FILE}")
        return
    
    # 1. 登录
    print("\n1. 登录...")
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json=login_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            print(f"❌ 登录失败: {response.status_code}")
            print(response.text)
            return
        
        data = response.json()
        if not data.get('success'):
            print(f"❌ 登录失败: {data.get('message')}")
            return
        
        user_id = data['user']['id']
        print(f"✅ 登录成功，用户ID: {user_id}")
    except Exception as e:
        print(f"❌ 登录异常: {e}")
        return
    
    # 2. 上传文件
    print("\n2. 上传文件...")
    
    try:
        with open(TEST_FILE, 'rb') as f:
            files = {'file': ('3122059历史翻译.DOC', f, 'application/msword')}
            response = requests.post(
                f"{BASE_URL}/api/import/upload",
                files=files
            )
        
        print(f"响应状态: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ 上传失败: {response.status_code}")
            print(response.text)
            return
        
        data = response.json()
        
        if not data.get('success'):
            print(f"❌ 上传失败: {data.get('error')}")
            return
        
        print(f"✅ 上传成功!")
        print(f"文件名: {data.get('filename')}")
        print(f"检测到 {data.get('total_pairs')} 对双语内容")
        print(f"分析信息: {data.get('analysis')}")
        
        if data.get('message'):
            print(f"提示: {data.get('message')}")
        
        # 显示检测到的对
        pairs = data.get('pairs', [])
        print(f"\n前10对预览:")
        for pair in pairs[:10]:
            source = pair['source'][:50] + "..." if len(pair['source']) > 50 else pair['source']
            target = pair['target'][:50] + "..." if len(pair['target']) > 50 else pair['target']
            print(f"  [{pair['index']}] [{pair['method']}] {source}")
            print(f"      -> {target}")
        
        filepath = data.get('filepath')
        
    except Exception as e:
        print(f"❌ 上传异常: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 3. 处理导入
    print("\n3. 处理导入...")
    
    try:
        import_data = {
            'filename': data.get('filename'),
            'filepath': filepath,
            'pairs': pairs[:10],  # 只导入前10对进行测试
            'terms': []
        }
        
        response = requests.post(
            f"{BASE_URL}/api/import/process",
            json=import_data,
            headers={
                "Content-Type": "application/json",
                "X-User-ID": str(user_id)
            }
        )
        
        print(f"响应状态: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ 处理失败: {response.status_code}")
            print(response.text)
            return
        
        result = response.json()
        
        if result.get('success'):
            print(f"✅ 导入成功!")
            print(f"导入的句段: {result.get('imported_segments')}")
            print(f"提取的术语: {result.get('imported_terms')}")
        else:
            print(f"❌ 处理失败: {result.get('error')}")
    
    except Exception as e:
        print(f"❌ 处理异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_import_api()
