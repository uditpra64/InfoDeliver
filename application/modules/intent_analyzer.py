import json
import logging
import re
from typing import Dict, Union, Any

from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)

prompt_template = """
# 会話文脈
{history_text}

# 現在のユーザー入力
User: {user_input}

# 現在使えるタスク
{task_info}

# タスク
上記の会話文脈とユーザー入力から、ユーザーの意図を解析してください。
以下のいずれかの形式でJSONとして返してください：

- 給与計算タスク開始: {{"intent": "task_start", "task_name": "task1 | task2 | ..."}}
- 質問、紹介、問い合わせ: {{"intent": "question", "query": "ユーザー入力"}}
- ファイルアップロード: {{"intent": "file_upload", "file_type": "ファイル種類"}}
- 確認応答: {{"intent": "confirmation", "response": true/false}}
- メニューに戻る: {{"intent": "return_to_menu"}}
- 他: {{"intent": "unknown"}}

# 出力形式
JSON形式のみを出力してください。
"""


class IntentAnalyzer:
    """
    ユーザー入力の意図をLLMで解析し、JSONデータとして返すエージェント。
    """

    def __init__(self, llm):
        self.llm = llm
        self.operation_list = [
            "general introduction",
            "advice",
            "selection",
            "generation",
            "comparison",
            "others",
        ]
        self.memory_pool = []

    def __call__(self, user_input: str, task_info: Dict[int, dict]) -> Dict:
        logger.debug("IntentAnalyzer呼び出し")
        prompt = prompt_template
        recent_chats = self.memory_pool[-3:]
        history_text = "\n".join(f"{h['role']}: {h['content']}" for h in recent_chats)

        task_info_text = " | ".join(task_info.keys())
        prompt = prompt.format(
            history_text=history_text, user_input=user_input, task_info=task_info_text
        )

        logger.debug(f"IntentAnalyzerのプロンプト:\n{prompt}")
        response = self.llm.invoke(prompt)
        response_dict = self._handle_response(response)
        logger.debug(f"IntentAnalyzerの解析結果: {response_dict}")

        self.memory_pool.append({"role": "human", "content": user_input})
        self.memory_pool.append(
            {"role": "AI", "content": f"意図={response_dict['intent']}"}
        )
        return response_dict

    def _handle_response(self, response: Union[str, Any]):
        """LLMからのレスポンスをJSONとしてパースしintentを取り出す"""
        try:
            # Handle both string responses and objects with content attribute
            content_str = ""
            if isinstance(response, str):
                content_str = response
            elif hasattr(response, 'content'):
                content_str = response.content
            else:
                content_str = str(response)
            
            # Find JSON pattern in content
            match = re.search(r"\{.*\}", content_str)
            if not match:
                raise ValueError("No JSON pattern found in response")
            
            json_str = match.group(0)
            response_dict = json.loads(json_str)
            _ = response_dict["intent"]  # intentキーがあるかチェック
            
        except Exception:
            logger.exception(
                "IntentAnalyzer解析中にエラーが発生。レスポンスをunknownにフォールバック"
            )
            response_dict = {"intent": "unknown"}
            
        return response_dict