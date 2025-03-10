from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum
import pandas as pd
from datetime import datetime
import json

# データクラスの定義
@dataclass
class FileSummary:
    file_type: str
    record_count: int
    target_year_month: Optional[str] = None
    warnings: List[str] = None
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.details is None:
            self.details = {}

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]

@dataclass
class CalculationSummary:
    target_year_month: str
    employee_count: int
    department_count: int
    total_work_days: int
    overtime_hours: float
    special_cases: List[str]

class TaskType(Enum):
    SALARY = "salary_calculation"
    BONUS = "bonus_calculation"
    COMMUTE = "commute_calculation"

class TaskManager:
    def __init__(self):
        self.task_definitions = {
            TaskType.SALARY: {
                "name": "給与計算",
                "required_files": [
                    {"type": "employee_master", "name": "従業員マスタ", "required": True},
                    {"type": "work_record", "name": "勤怠データ", "required": True},
                    {"type": "allowance_master", "name": "手当マスタ", "required": True}
                ]
            },
            # 他のタスク定義も同様に追加
        }
        
        self.active_task: Optional[TaskType] = None
        self.file_summaries: Dict[str, FileSummary] = {}
        self.calculation_summary: Optional[CalculationSummary] = None
        self.uploaded_files: Dict[str, str] = {}  # ファイルパスを保存

    def start_task(self, task_type: TaskType) -> Dict[str, Any]:
        """タスクを開始し、必要なファイル情報を返す"""
        if task_type not in self.task_definitions:
            raise ValueError("未定義のタスク種類です")
        
        self.active_task = task_type
        self.file_summaries.clear()
        self.calculation_summary = None
        
        return {
            "task_info": self.task_definitions[task_type],
            "required_files": self.get_required_files()
        }

    def handle_file_upload(
        self, 
        file_type: str, 
        file_path: str, 
        validation_result: ValidationResult,
        file_summary: FileSummary
    ) -> Dict[str, Any]:
        """ファイルアップロードの処理"""
        if not self.active_task:
            return {"success": False, "message": "タスクが開始されていません"}

        task_def = self.task_definitions[self.active_task]
        file_config = next(
            (f for f in task_def["required_files"] if f["type"] == file_type),
            None
        )

        if not file_config:
            return {"success": False, "message": f"このタスクでは{file_type}は必要ありません"}

        self.file_summaries[file_type] = file_summary
        self.uploaded_files[file_type] = file_path

        # 全ファイルが揃った時点でサマリーを生成
        if self.is_ready_to_execute():
            self.calculation_summary = self.generate_calculation_summary()

        return {
            "success": True,
            "task_progress": self.get_task_progress(),
            "validation_result": validation_result
        }

    def generate_calculation_summary(self) -> Optional[CalculationSummary]:
        """計算実行前のサマリー情報を生成"""
        if not self.active_task or not self.is_ready_to_execute():
            return None

        if self.active_task == TaskType.SALARY:
            emp_summary = self.file_summaries["employee_master"]
            work_summary = self.file_summaries["work_record"]

            return CalculationSummary(
                target_year_month=work_summary.target_year_month,
                employee_count=emp_summary.record_count,
                department_count=len(emp_summary.details.get("departments", [])),
                total_work_days=work_summary.details.get("total_work_days", 0),
                overtime_hours=work_summary.details.get("total_overtime_hours", 0.0),
                special_cases=self.get_special_cases()
            )
        
        return None

    def get_special_cases(self) -> List[str]:
        """特殊ケースの一覧を取得"""
        special_cases = []
        for file_summary in self.file_summaries.values():
            special_cases.extend(file_summary.warnings)
        return special_cases

class PayrollCalculator:
    """給与計算実行クラス"""
    def calculate(self, task_type: TaskType, files: Dict[str, str]) -> Dict[str, Any]:
        try:
            # 実際の計算ロジックを実装
            if task_type == TaskType.SALARY:
                return self._calculate_salary(files)
            # 他の計算タイプも同様に実装
            
            raise ValueError("未対応の計算タイプです")
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": getattr(e, "details", [])
            }

    def _calculate_salary(self, files: Dict[str, str]) -> Dict[str, Any]:
        """給与計算の実行"""
        try:
            # ファイルの読み込み
            emp_df = pd.read_csv(files["employee_master"])
            work_df = pd.read_csv(files["work_record"])
            allowance_df = pd.read_csv(files["allowance_master"])

            # 計算処理（実際の実装はビジネスロジックに応じて）
            result_df = self._process_salary_calculation(
                emp_df, work_df, allowance_df
            )

            # 結果ファイルの生成
            output_path = f"payroll_result_{datetime.now():%Y%m}.xlsx"
            result_df.to_excel(output_path, index=False)

            return {
                "success": True,
                "output_file": output_path,
                "summary": {
                    "processed_count": len(result_df),
                    "total_amount": result_df["salary_amount"].sum()
                }
            }

        except Exception as e:
            raise RuntimeError(f"給与計算処理でエラーが発生: {str(e)}")

class PayrollAgent:
    """給与計算エージェントメインクラス"""
    def __init__(self):
        self.task_manager = TaskManager()
        self.calculator = PayrollCalculator()

    async def handle_user_input(self, input_text: str) -> str:
        """ユーザー入力の処理"""
        # LLMを使用してintentを解析
        intent = await self.analyze_intent(input_text)
        
        if intent["intent"] == "task_start":
            return self.start_task(TaskType(intent["task_name"]))
        elif intent["intent"] == "file_upload":
            return await self.handle_file_upload(intent["file_type"], intent["file_path"])
        elif intent["intent"] == "confirmation":
            return await self.handle_confirmation(intent["response"])
        
        return "ご要望を理解できませんでした。もう一度お願いできますか？"

    async def handle_confirmation(self, confirmed: bool) -> str:
        """確認応答の処理"""
        if not confirmed:
            return "処理を中断しました。他にご要望はありますか？"

        if not self.task_manager.is_ready_to_execute():
            return "必要なファイルが揃っていないため、処理を開始できません。"

        summary = self.task_manager.calculation_summary
        if summary:
            # サマリー情報の表示
            confirmation_message = self.create_confirmation_message(summary)
            await self.send_message(confirmation_message)
            return "上記の内容で計算を実行してよろしいですか？（はい/いいえ）"

        # 計算の実行
        return await self.execute_calculation()

    def create_confirmation_message(self, summary: CalculationSummary) -> str:
        """確認メッセージの生成"""
        messages = [
            "【計算実行前の確認事項】",
            f"対象年月: {summary.target_year_month}",
            f"対象社員数: {summary.employee_count}名",
            f"部門数: {summary.department_count}部門",
            f"勤務日数: {summary.total_work_days}日",
            f"総残業時間: {summary.overtime_hours}時間"
        ]

        if summary.special_cases:
            messages.append("\n【注意事項】")
            messages.extend(f"- {case}" for case in summary.special_cases)

        return "\n".join(messages)

    async def execute_calculation(self) -> str:
        """計算の実行"""
        await self.send_message("計算処理を開始します。しばらくお待ちください...")

        result = self.calculator.calculate(
            self.task_manager.active_task,
            self.task_manager.uploaded_files
        )

        if result["success"]:
            messages = [
                "計算が完了しました。",
                f"結果ファイル: {result['output_file']}"
            ]
            
            if "messages" in result:
                messages.append("\n処理結果:")
                messages.extend(f"- {msg}" for msg in result["messages"])
            
            return "\n".join(messages)
        else:
            return self.format_error_message(result)

    async def send_message(self, message: str):
        """メッセージ送信（実際の実装ではWebSocketなどを使用）"""
        print(message)  # デモ用の簡易実装

# 使用例
async def main():
    agent = PayrollAgent()
    
    # タスク開始
    response = await agent.handle_user_input("給与計算を開始")
    print(response)
    
    # ファイルアップロード
    response = await agent.handle_user_input("従業員マスタをアップロード")
    print(response)
    
    # 確認
    response = await agent.handle_user_input("はい")
    print(response)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
