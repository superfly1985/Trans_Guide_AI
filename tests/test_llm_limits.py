# -*- coding: utf-8 -*-
"""
测试 MiniMax LLM 的文本长度上限
"""

import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.llm_client import LLMClient


def test_llm_with_length(text_length: int) -> dict:
    """测试特定文本长度的 LLM 调用"""
    
    # 生成测试文本（中英文混合）
    base_text = """Work Instruction 作业指导书
Process Release 过程放行
Quality Assurance 质量保证
Checkpoints 检查点
Series Production 批量生产
Initial Sample 初始样品
Modular Harness 模块型线束
Change Notification 变更通知
Preliminary Release 临时放行
Internal Release 内部放行
Overall Release 最终放行
"""
    
    # 重复文本以达到指定长度
    repeat_count = (text_length // len(base_text)) + 1
    test_text = (base_text * repeat_count)[:text_length]
    
    print(f"\n{'='*60}")
    print(f"测试文本长度: {len(test_text)} 字符")
    print(f"{'='*60}")
    
    try:
        client = LLMClient()
        
        prompt = f"""从以下文档中提取专业术语（英文-中文对照），最多返回10个：

文档内容：
{test_text}

请以JSON格式返回：
{{
    "terms": [
        {{"english": "术语", "chinese": "译法", "category": "分类"}}
    ]
}}"""
        
        print(f"提示词总长度: {len(prompt)} 字符")
        print("发送请求...")
        
        start_time = time.time()
        response = client.generate(prompt, max_tokens=1000, temperature=0.3)
        elapsed_time = time.time() - start_time
        
        print(f"✅ 成功! 响应长度: {len(response)} 字符")
        print(f"⏱️  耗时: {elapsed_time:.2f} 秒")
        print(f"响应预览: {response[:200]}...")
        
        return {
            "success": True,
            "text_length": text_length,
            "prompt_length": len(prompt),
            "response_length": len(response),
            "elapsed_time": elapsed_time,
            "response": response
        }
        
    except Exception as e:
        print(f"❌ 失败: {e}")
        return {
            "success": False,
            "text_length": text_length,
            "error": str(e)
        }


def main():
    """主测试函数"""
    
    print("="*60)
    print("MiniMax LLM 文本长度上限测试")
    print("="*60)
    
    # 测试不同的文本长度
    test_lengths = [
        1000,    # 1K
        5000,    # 5K
        10000,   # 10K
        20000,   # 20K
        30000,   # 30K
        50000,   # 50K
        80000,   # 80K
        100000,  # 100K
    ]
    
    results = []
    
    for length in test_lengths:
        result = test_llm_with_length(length)
        results.append(result)
        
        if not result["success"]:
            print(f"\n⚠️  在 {length} 字符处失败，停止测试")
            break
        
        # 等待一下避免请求过快
        time.sleep(2)
    
    # 打印总结
    print("\n" + "="*60)
    print("测试结果总结")
    print("="*60)
    
    for r in results:
        if r["success"]:
            print(f"✅ {r['text_length']:>6} 字符 - 成功 ({r['elapsed_time']:.1f}s)")
        else:
            print(f"❌ {r['text_length']:>6} 字符 - 失败: {r.get('error', 'Unknown')}")
    
    # 找出最大成功长度
    successful_lengths = [r["text_length"] for r in results if r["success"]]
    if successful_lengths:
        print(f"\n📊 最大成功文本长度: {max(successful_lengths)} 字符")


if __name__ == "__main__":
    main()
