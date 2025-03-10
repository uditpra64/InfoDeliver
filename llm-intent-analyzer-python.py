from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Literal
from enum import Enum
import json
import asyncio
from datetime import datetime

class IntentType(Enum):
    TASK_START = "task_start"
    QUESTION = "question"
    FILE_UPLOAD = "file_upload"
    CONFIRMATION = "confirmation"
    RETURN_TO_MENU = "return_to_menu"
    UNKNOWN = "unknown"

@dataclass
class ConversationContext:
    last_intent: Optional[IntentType] = None
    current_task: Optional[str] = None
    last_message: Optional[str] = None
    conversation_state: str = "init"

@dataclass
class IntentAnalysisResult:
    intent_type: IntentType
    confidence: float
    params: Dict[str, Any]
    context: ConversationContext

class LLMIntentAnalyzer:
    def __init__(self):
        self.conversation_history: List[Dict[str, str]] = []
        self.context = ConversationContext()
        
        # インテントに必要なパラメータの定義
        self.intent_params = {
            IntentType.TASK_START: ["task_name"],
            IntentType.QUESTION: ["query"],
            IntentType.FILE_UPLOAD: ["file_type"],
            IntentType.CONFIRMATION: ["response"],
            IntentType.RETURN_TO_MENU: []
        }

    def _create_prompt(self, user_input: str) -> str:
        """LLMへのプロンプトを生成"""
        # 直近の会話履歴を取得（最大3件）
        recent_history = self.conversation_history[-3:] if self.conversation_history else []
        
        # 会話履歴の整形
        history_text = "\n".join(
            f"{h['role']}: {h['content']}" 
            for h in recent_history
        )

        # プロンプトの構築
        prompt = f"""
# 会話文脈
{history_text}

# 現在のユーザー入力
User: {user_input}

# 現在の状態
{self.context.conversation_state}

# タスク
上記の会話文脈とユーザー入力から、ユーザーの意図を解析してください。
以下のいずれかの形式でJSONとして返してください：

- 給与計算タスク開始: {{"intent": "task_start", "task_name": "salary_calculation"}}
- 質問: {{"intent": "question", "query": "質問内容"}}
- ファイルアップロード: {{"intent": "file_upload", "file_type": "ファイル種類"}}
- 確認応答: {{"intent": "confirmation", "response": true/false}}
- メニューに戻る: {{"intent": "return_to_menu"}}

# 出力形式
JSONのみを出力してください。
"""
        return prompt

    async def _call_llm(self, prompt: str) -> str:
        """LLM APIの呼び出し
        実際の実装では、使用するLLMのAPIに応じて実装"""
        # サンプルのレスポンス（実際の実装では削除）
        sample_responses = {
            "1": '{"intent": "task_start", "task_name": "salary_calculation"}',
            "2": '{"intent": "question", "query": "general"}',
            "給与計算を開始": '{"intent": "task_start", "task_name": "salary_calculation"}',
            "はい": '{"intent": "confirmation", "response": true}',
            "いいえ": '{"intent": "confirmation", "response": false}',
            "従業員マスタをアップロード": '{"intent": "file_upload", "file_type": "employee_master"}'
        }
        
        # 実際のLLM呼び出しをシミュレート（遅延を追加）
        await asyncio.sleep(0.1)
        return sample_responses.get(prompt.strip(), '{"intent": "unknown"}')

    def _update_context(self, intent_result: Dict[str, Any]) -> None:
        """会話コンテキストの更新"""
        intent_type = IntentType(intent_result["intent"])
        
        # インテントに基づいてステート遷移
        if intent_type == IntentType.TASK_START:
            self.context.conversation_state = "task_selection"
            self.context.current_task = intent_result.get("task_name")
        elif intent_type == IntentType.FILE_UPLOAD:
            self.context.conversation_state = "file_upload"
        elif intent_type == IntentType.RETURN_TO_MENU:
            self.context.conversation_state = "main_menu"
            self.context.current_task = None
        
        self.context.last_intent = intent_type
        self.context.last_message = json.dumps(intent_result)

    async def analyze_intent(self, user_input: str) -> IntentAnalysisResult:
        """ユーザー入力からインテントを分析"""
        try:
            # プロンプトの生成
            prompt = self._create_prompt(user_input)
            
            # LLMの呼び出し
            llm_response = await self._call_llm(user_input)
            
            # レスポンスのパース
            intent_result = json.loads(llm_response)
            
            # コンテキストの更新
            self._update_context(intent_result)
            
            # 会話履歴への追加
            self.conversation_history.append({
                "role": "user",
                "content": user_input,
                "timestamp": datetime.now().isoformat(),
                "intent": intent_result
            })

            # 結果の生成
            return IntentAnalysisResult(
                intent_type=IntentType(intent_result["intent"]),
                confidence=0.9,  # LLMからの確信度を取得できる場合は使用
                params={
                    k: v for k, v in intent_result.items()
                    if k != "intent"
                },
                context=self.context
            )

        except json.JSONDecodeError:
            return IntentAnalysisResult(
                intent_type=IntentType.UNKNOWN,
                confidence=0.0,
                params={},
                context=self.context
            )
        except Exception as e:
            print(f"Error in intent analysis: {str(e)}")
            return IntentAnalysisResult(
                intent_type=IntentType.UNKNOWN,
                confidence=0.0,
                params={"error": str(e)},
                context=self.context
            )

class PayrollAgentIntentHandler:
    """給与計算エージェント用のインテントハンドラ"""
    def __init__(self):
        self.intent_analyzer = LLMIntentAnalyzer()

    async def handle_user_input(self, user_input: str) -> str:
        """ユーザー入力の処理"""
        intent_result = await self.intent_analyzer.analyze_intent(user_input)
        
        # インテントに基づいて適切な処理を実行
        if intent_result.intent_type == IntentType.TASK_START:
            return self._handle_task_start(intent_result.params)
        elif intent_result.intent_type == IntentType.FILE_UPLOAD:
            return self._handle_file_upload(intent_result.params)
        elif intent_result.intent_type == IntentType.CONFIRMATION:
            return self._handle_confirmation(intent_result.params)
        elif intent_result.intent_type == IntentType.QUESTION:
            return await self._handle_question(intent_result.params)
        elif intent_result.intent_type == IntentType.RETURN_TO_MENU:
            return self._handle_return_to_menu()
        else:
            return "申し訳ありません。ご要望を理解できませんでした。もう一度お願いできますか？"

    def _handle_task_start(self, params: Dict[str, Any]) -> str:
        task_name = params.get("task_name")
        if task_name == "salary_calculation":
            return """
給与計算を開始します。
以下のファイルが必要です：
1. 従業員マスタ
2. 勤怠データ
3. 手当マスタ
いずれかのファイルをアップロードしてください。
"""
        return f"申し訳ありません。{task_name}は現在対応していません。"

    def _handle_file_upload(self, params: Dict[str, Any]) -> str:
        file_type = params.get("file_type")
        return f"{file_type}のアップロードを受け付けました。"

    def _handle_confirmation(self, params: Dict[str, Any]) -> str:
        response = params.get("response", False)
        if response:
            return "承知しました。処理を開始します。"
        return "処理を中断しました。他にご要望はありますか？"

    async def _handle_question(self, params: Dict[str, Any]) -> str:
        query = params.get("query", "")
        # 実際の実装では、RAGなどを使用して回答を生成
        return f"申し訳ありません。現在{query}に関する回答を準備中です。"

    def _handle_return_to_menu(self) -> str:
        return """
メインメニューに戻りました。
以下からお選びください：
1. 給与計算を開始
2. 質問をする
"""

# 使用例
async def main():
    agent = PayrollAgentIntentHandler()
    
    # メニュー選択
    response = await agent.handle_user_input("1")
    print("System:", response)
    
    # ファイルアップロード
    response = await agent.handle_user_input("従業員マスタをアップロードします")
    print("System:", response)
    
    # 質問
    response = await agent.handle_user_input("残業代の計算方法について教えて")
    print("System:", response)

if __name__ == "__main__":
    asyncio.run(main())
