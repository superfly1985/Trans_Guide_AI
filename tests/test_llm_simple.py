# -*- coding: utf-8 -*-
"""
测试 LLM 简单请求
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.llm_client import LLMClient


def test_simple_llm():
    """测试简单的 LLM 请求"""
    
    print("=" * 60)
    print("测试 LLM 简单请求")
    print("=" * 60)
    
    try:
        print("\n1. 初始化 LLM 客户端...")
        llm_client = LLMClient()
        print("✅ 初始化成功")
        
        print("\n2. 检查可用性...")
        if llm_client.is_available():
            print("✅ LLM 可用")
        else:
            print("❌ LLM 不可用")
            return
        
        print("\n3. 发送简单请求...")
        prompt = "提取术语：Work Instruction - 作业指导书，Quality Assurance - 质量保证。只返回 'OK'"
        print(f"提示词: {prompt}")
        
        response = llm_client.generate(prompt, max_tokens=10, temperature=0.3)
        print(f"✅ 收到响应: {response}")
        
        print("\n4. 发送术语提取请求...")
        prompt2 = """从以下文本提取术语：
Work Instruction 作业指导书
Process Release 过程放行
Quality Assurance 质量保证

返回JSON格式：{"terms":[{"english":"Work Instruction","chinese":"作业指导书"}]}"""
        
        response2 = llm_client.generate(prompt2, max_tokens=200, temperature=0.3)
        print(f"✅ 收到响应: {response2[:200]}...")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_simple_llm()
