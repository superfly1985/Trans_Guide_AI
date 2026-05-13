import json
import sys
import time

sys.path.insert(0, ".")

def test_connectivity():
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    api_cfg = config["api"]
    base_url = api_cfg["base_url"]
    api_key = api_cfg["api_key"]
    model_name = api_cfg["model_name"]

    print(f"=== 模型连通性测试 ===")
    print(f"Base URL : {base_url}")
    print(f"Model    : {model_name}")
    print(f"API Key  : {api_key[:10]}...{api_key[-6:]}")
    print()

    try:
        from openai import OpenAI
    except ImportError:
        print("[FAIL] openai 库未安装，请运行: pip install openai")
        return False

    client = OpenAI(base_url=base_url, api_key=api_key)

    models_to_test = ["MiniMax-M2.7", "MiniMax-M2.5", "MiniMax-M2.1"]

    for model in models_to_test:
        print(f"--- 测试模型: {model} ---")
        try:
            start = time.time()
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "请用一句话回复：模型连通正常"}
                ],
                max_tokens=100,
                temperature=0.3
            )
            elapsed = time.time() - start
            content = response.choices[0].message.content
            usage = response.usage
            print(f"  状态  : ✅ 连通成功")
            print(f"  耗时  : {elapsed:.2f}s")
            print(f"  回复  : {content}")
            print(f"  Tokens: prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}")
        except Exception as e:
            print(f"  状态  : ❌ 连接失败")
            print(f"  错误  : {e}")
        print()

    return True

if __name__ == "__main__":
    test_connectivity()
