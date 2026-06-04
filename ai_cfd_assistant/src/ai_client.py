"""DeepSeek API client with streaming support."""

from __future__ import annotations
import os
from openai import OpenAI


SYSTEM_PROMPT = """你是一位资深的计算流体力学(CFD)和空气动力学专家，拥有20年飞行器设计经验。你的角色是帮助用户理解和分析CFD相关的概念、方法和结果。

你的专业领域包括：
- 翼型理论与设计（NACA系列、超临界翼型等）
- 面元法(Panel Method)和势流理论
- 有限体积法(FVM)和SIMPLE算法
- 湍流模型（k-epsilon, k-omega SST等）
- 边界层理论和转捩
- 地面效应空气动力学
- FSAE赛车空气动力学
- 网格生成技术

回答要求：
1. 用中文回答，专业术语保留英文
2. 提供数学公式时用LaTeX格式（$...$ 或 $$...$$）
3. 涉及翼型参数时，主动建议用户切换右侧可视化面板查看
4. 回答既要有理论深度，又要让大一学生能听懂
5. 当用户询问具体计算时，给出可执行的步骤
6. 适当使用代码块展示伪代码或Python示例

当前你正在一个集成了CFD可视化工具的桌面应用中运行。用户可以在右侧面板查看翼型形状、压力系数分布和流线图。
当用户讨论某个具体翼型时，建议他们在面板中调整参数来实时观察变化。"""


class AIClient:
    """DeepSeek API client via OpenAI-compatible interface."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com/v1",
        )

    def chat_stream(self, messages: list[dict], model: str = "deepseek-chat"):
        """Return a streaming iterator for chat completions."""
        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        response = self.client.chat.completions.create(
            model=model,
            messages=full_messages,
            stream=True,
            temperature=0.7,
            max_tokens=4096,
        )
        return response

    def chat(self, messages: list[dict], model: str = "deepseek-chat") -> str:
        """Non-streaming chat completion."""
        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        response = self.client.chat.completions.create(
            model=model,
            messages=full_messages,
            temperature=0.7,
            max_tokens=4096,
        )
        return response.choices[0].message.content
