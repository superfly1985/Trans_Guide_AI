快速开始
​
1. 安装 OpenAI SDK

Python

Node.js
pip install openai
​
2. 配置环境变量
export OPENAI_BASE_URL=https://api.minimaxi.com/v1
export OPENAI_API_KEY=${YOUR_API_KEY}
​
3. 调用 API
Python
from openai import OpenAI

client = OpenAI()

response = client.chat.completions.create(
    model="MiniMax-M2.7",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hi, how are you?"},
    ],
    # 设置 reasoning_split=True 将思考内容分离到 reasoning_details 字段
    extra_body={"reasoning_split": True},
)

print(f"Thinking:\n{response.choices[0].message.reasoning_details[0]['text']}\n")
print(f"Text:\n{response.choices[0].message.content}\n")
​
4. 特别注意
在多轮 Function Call 对话中，必须将完整的模型返回（即 assistant 消息）添加到对话历史，以保持思维链的连续性：
将完整的 response_message 对象（包含 tool_calls 字段）添加到消息历史
原生的OpenAI API 的 MiniMax-M2.7 MiniMax-M2.7-highspeed MiniMax-M2.5 MiniMax-M2.5-highspeed MiniMax-M2.1 MiniMax-M2.1-highspeed MiniMax-M2 模型 content 字段会包含 <think> 标签内容，需要完整保留
在 Interleaved Thinking 友好格式中，通过启用额外的参数(reasoning_split=True)，模型思考内容通过 reasoning_details 字段单独提供，同样需要完整保留
​
支持的模型
使用 OpenAI SDK 时，支持以下 MiniMax 模型：
模型名称	上下文窗口	模型介绍
MiniMax-M2.7	204,800	开启模型的自我迭代（输出速度约 60 TPS）