# -*- coding: utf-8 -*-
"""
测试添加术语功能
"""

import requests
import json

BASE_URL = "http://127.0.0.1:5555"

def test_add_term():
    """测试添加术语 API"""
    
    # 1. 先登录获取用户ID
    print("=" * 50)
    print("1. 测试登录")
    print("=" * 50)
    
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
        print(f"登录响应状态: {response.status_code}")
        print(f"登录响应内容: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                user_id = data['user']['id']
                print(f"登录成功，用户ID: {user_id}")
            else:
                print(f"登录失败: {data.get('message')}")
                # 尝试注册
                print("\n尝试注册...")
                register_data = {
                    "username": "admin",
                    "password": "admin123",
                    "email": "admin@test.com"
                }
                response = requests.post(
                    f"{BASE_URL}/api/auth/register",
                    json=register_data,
                    headers={"Content-Type": "application/json"}
                )
                print(f"注册响应: {response.text}")
                return
        else:
            print(f"登录请求失败: {response.status_code}")
            return
    except Exception as e:
        print(f"登录异常: {e}")
        return
    
    # 2. 测试添加术语
    print("\n" + "=" * 50)
    print("2. 测试添加术语")
    print("=" * 50)
    
    term_data = {
        "source": "test_term",
        "target": "测试术语",
        "category": "test",
        "tags": "test,example",
        "notes": "这是一个测试术语"
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-User-ID": str(user_id)
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/terms",
            json=term_data,
            headers=headers
        )
        print(f"添加术语响应状态: {response.status_code}")
        print(f"添加术语响应内容: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ 术语添加成功!")
            else:
                print(f"❌ 术语添加失败: {data.get('error')}")
        else:
            print(f"❌ 请求失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 添加术语异常: {e}")
    
    # 3. 测试获取术语列表
    print("\n" + "=" * 50)
    print("3. 测试获取术语列表")
    print("=" * 50)
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/terms",
            headers=headers
        )
        print(f"获取术语列表响应状态: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                terms = data.get('terms', [])
                print(f"✅ 获取术语列表成功，共 {len(terms)} 个术语")
                for term in terms[:5]:  # 只显示前5个
                    print(f"  - {term.get('source')} -> {term.get('target')}")
            else:
                print(f"❌ 获取术语列表失败: {data.get('error')}")
        else:
            print(f"❌ 请求失败: {response.status_code}")
            print(f"响应内容: {response.text}")
    except Exception as e:
        print(f"❌ 获取术语列表异常: {e}")

if __name__ == "__main__":
    test_add_term()
