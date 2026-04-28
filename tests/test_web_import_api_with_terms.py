# -*- coding: utf-8 -*-
"""
测试 Web 导入 API - 包含术语导入
"""

import requests
import os

BASE_URL = "http://127.0.0.1:5555"
TEST_FILE = r"d:\01.AwesomeProject\52.Trans_Guide_AI\tests\test_doc\3122059历史翻译.DOC"


def test_import_api_with_terms():
    """测试导入 API - 导入术语"""
    
    print("=" * 60)
    print("测试 Web 导入 API - 术语导入")
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
        
        if response.status_code != 200:
            print(f"❌ 上传失败: {response.status_code}")
            return
        
        data = response.json()
        
        if not data.get('success'):
            print(f"❌ 上传失败: {data.get('error')}")
            return
        
        print(f"✅ 上传成功!")
        print(f"检测到 {data.get('total_terms')} 个术语（LLM 提取）")
        print(f"检测到 {data.get('total_pairs')} 对双语内容")
        
        filepath = data.get('filepath')
        filename = data.get('filename')
        
        # 显示 LLM 提取的术语
        terms = data.get('potential_terms', [])
        if terms:
            print(f"\nLLM 提取的术语:")
            for term in terms[:10]:
                print(f"  - {term['english']} -> {term['chinese']}")
                if term.get('category'):
                    print(f"    分类: {term['category']}")
        else:
            print("\n⚠️ LLM 未提取到术语（可能 LLM 不可用）")
            # 使用模拟术语进行测试
            terms = [
                {"english": "Work Instruction", "chinese": "作业指导书", "category": "文档类型"},
                {"english": "Process Release", "chinese": "过程放行", "category": "流程"},
                {"english": "Quality Assurance", "chinese": "质量保证", "category": "质量"},
                {"english": "Series Production", "chinese": "批量生产", "category": "生产"},
            ]
            print("使用模拟术语进行测试...")
        
    except Exception as e:
        print(f"❌ 上传异常: {e}")
        return
    
    # 3. 处理导入 - 只导入术语
    print("\n3. 处理导入（术语）...")
    
    try:
        import_data = {
            'filename': filename,
            'filepath': filepath,
            'pairs': [],  # 不导入句段
            'terms': terms[:4]  # 导入前4个术语
        }
        
        response = requests.post(
            f"{BASE_URL}/api/import/process",
            json=import_data,
            headers={
                "Content-Type": "application/json",
                "X-User-ID": str(user_id)
            }
        )
        
        if response.status_code != 200:
            print(f"❌ 处理失败: {response.status_code}")
            print(response.text)
            return
        
        result = response.json()
        
        if result.get('success'):
            print(f"✅ 导入成功!")
            print(f"导入的术语: {result.get('imported_terms')}")
            print(f"导入的句段: {result.get('imported_segments')}")
        else:
            print(f"❌ 处理失败: {result.get('error')}")
    
    except Exception as e:
        print(f"❌ 处理异常: {e}")


if __name__ == "__main__":
    test_import_api_with_terms()
