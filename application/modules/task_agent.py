import importlib
import os
import re
import tempfile
import traceback
from datetime import datetime
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
from transitions import Machine, State

from application.modules.chat_agent import ChatAgent
from application.modules.code_agent import CodeAgent
from application.modules.file_agent import FileAgent


class FileState(State):
    """
    TaskAgentにおけるファイル処理用State拡張。
    現在のファイルインデックスなどを保持。
    """

    def __init__(
        self, name, on_enter=..., on_exit=..., ignore_invalid_triggers=..., final=...
    ):
        super().__init__(name, on_enter, on_exit, ignore_invalid_triggers, final)
        self.current_file_idx = 0

    def forward_current_file_idx(self):
        self.current_file_idx += 1

    def reset(self):
        self.current_file_idx = 0


class TaskAgent:
    """
    単一の給与計算タスクを処理するエージェント。
    各ステップ（ファイルチェック、分析、コード生成、テスト、処理実行など）を
    状態に応じたモジュール化されたメソッドで実装。
    """

    def __init__(
        self, config: dict, file_agent: FileAgent, llm_code=None, llm_chat=None, idx=0
    ):
        self.name = config.get("名称", "")
        self.description = config.get("概要", "")
        self.files, self.files_optional = self._check_file_necessity(config)
        self.total_file_num = len(self.files) + len(self.files_optional)
        self.file_num = len(self.files)
        self.next_task_name = config.get("次のタスク名前", None)
        self.next_task_replaced_file_name = config.get(
            "次のタスクで交換されるファイル", None
        )
        self.next_task_replaced_file_definition = config.get(
            "次のタスクで交換されるファイル定義", None
        )
        self.next_task_replaced_file_output_usage = config.get(
            "次のタスクで交換されるファイル出力用", False
        )
        self.replaced_file_name = None
        self.replaced_file_path = None

        self.saved_file_path = None
        self.prompt_file = config.get("ルール", "")
        self.function_name = f"data_processing_{idx}"
        self.file_agent = file_agent
        self.file_ids = {}
        self.results = {}

        self.current_date = None
        self.generated_func = None
        self.staff_codes = None
        self.prompt_content = None

        self.fast_mode: bool = False
        self.llm_code = llm_code
        self.llm_chat = llm_chat
        self.code_agent = CodeAgent(llm_code)
        self.chat_agent = ChatAgent(llm_chat)

        self._create_state_machine()

    def _create_state_machine(self):
        """タスク処理用の状態機械を構築"""
        self.file_state = FileState("file")
        states = [
            "prepare",
            self.file_state,
            "analysis",
            "date",
            "process",
            "test",
            "work",
            "revise",
            "continue",
            "over",
        ]
        self.state_machine = Machine(states=states, initial="prepare")

    def _check_file_necessity(self, config: dict) -> Tuple[List[dict], List[dict]]:
        files = []
        files_opt = []
        for file_info in config.get("必要なファイル", []):
            if file_info.get("出力用", False):
                files.append(file_info)
            else:
                if file_info.get("必要", True):
                    files.append(file_info)
                else:
                    files_opt.append(file_info)
        return files, files_opt

    def get_description(self) -> str:
        return self.description

    def get_files(self) -> List[str]:
        return [f["ファイル名前"] for f in self.files]

    def get_current_state(self) -> str:
        return self.state_machine.state

    def set_fast_mode(self):
        self.fast_mode = True

    def set_normal_mode(self):
        self.fast_mode = False

    def is_fast_mode(self) -> bool:
        return self.fast_mode

    def set_next_state(self) -> str:
        current_state = self.get_current_state()
        if not self.fast_mode:
            if current_state == "prepare":
                self.state_machine.set_state("file")
            elif current_state == "file":
                self.state_machine.set_state("analysis")
            elif current_state == "analysis":
                self.state_machine.set_state("process")
            elif current_state == "process":
                self.state_machine.set_state("test")
            elif current_state == "test":
                self.state_machine.set_state("work")
            elif current_state == "work":
                self.state_machine.set_state("revise")
            elif current_state == "revise":
                self.state_machine.set_state("continue")
            elif current_state == "continue":
                self.state_machine.set_state("over")
        else:
            if current_state == "prepare":
                self.state_machine.set_state("file")
            elif current_state == "file":
                self.state_machine.set_state("process")
            elif current_state == "process":
                self.state_machine.set_state("over")
        return self.get_current_state()

    def get_nextstep(self) -> Tuple[Optional[str], Optional[str]]:
        self.set_next_state()
        state = self.get_current_state()

        if state == "file":
            return "ファイルをファイルエージェントにチェックします。", "file"
        elif state == "analysis":
            return "分析を開始しますか？(Yes/スキップを入力)", "analysis"
        elif state == "process":
            if not self.is_fast_mode():
                return (
                    f"以下のルールで処理を開始しますか？(Yes/no)\n\n{self.prompt_content}",
                    "process",
                )
            else:
                return (
                    f"以下のルールで処理を開始します:\n\n{self.prompt_content}\nしばらくお待ちください",
                    "process",
                )
        elif state == "test":
            return (
                "指定した1つのスタッフコードのテストをスキップしますか？(Yes / スタッフコード)",
                "test",
            )
        elif state == "work":
            return "出力用のスタッフコードに使用しますか？(Yes/no)", "work"
        elif state == "revise":
            return "もう一度試す必要がありますか？(Yes/「スキップ」を入力)", "revise"
        elif state == "continue":
            return (
                f"次のタスク「{self.next_task_name}」に進みますか？(Yes/no)",
                "continue",
            )
        elif state == "over":
            return None, "over"

        return None, None

    def get_currentstep(self) -> Tuple[Optional[str], Optional[str]]:
        state = self.get_current_state()
        if state == "prepare":
            return "タスクの処理を開始しますか？", "prepare"
        elif state == "file":
            return "ファイルをファイルエージェントにチェックします。", "file"
        elif state == "analysis":
            return "分析を開始しますか？(Yes/スキップを入力)", "analysis"
        elif state == "process":
            if not self.is_fast_mode():
                return (
                    f"以下のルールで処理を開始しますか？(Yes/no)\n\n{self.prompt_content}",
                    "process",
                )
            else:
                return (
                    f"以下のルールで処理を開始します:\n{self.prompt_content}\nしばらくお待ちください",
                    "process",
                )
        elif state == "test":
            return (
                "指定した1つのスタッフコードのテストをスキップしますか？(Yes / スタッフコード)",
                "test",
            )
        elif state == "work":
            return "出力用のスタッフコードに使用しますか？(Yes/no)", "work"
        elif state == "revise":
            return "もう一度試す必要がありますか？(Yes/「スキップ」を入力)", "revise"
        elif state == "continue":
            return (
                f"次のタスク「{self.next_task_name}」に進みますか？(Yes/no)",
                "continue",
            )
        elif state == "over":
            return None, "over"

        return None, None

    # --- 各ステップの処理メソッド（モジュール化） ---
    def process_prepare(
        self, message: str
    ) -> Tuple[Optional[str | List[str]], Optional[str]]:
        yes_list = ["", "yes", "1", "true", "y", "はい", "そうです"]
        if message not in yes_list:
            return "「Yes」のメッセージをお待ちしています", None
        return self.get_nextstep()

    def process_analysis(
        self, message: str
    ) -> Tuple[Optional[str | List[str]], Optional[str]]:
        skip_list = ["スキップ", "skip"]
        yes_list = ["", "yes", "1", "true", "y", "はい", "そうです"]
        if message in skip_list:
            with open(self._get_rule_file_path(), "r", encoding="utf-8") as f:
                self.prompt_content = f.read()
            return self.get_nextstep()
        if message not in yes_list:
            return "「Yes」のメッセージをお待ちしています", None
        return self._analysis_files()

    def process_generation(
        self, message: str
    ) -> Tuple[Optional[str | List[str]], Optional[str]]:
        yes_list = ["", "yes", "1", "true", "y", "はい", "そうです"]
        if message not in yes_list:
            return "「Yes」のメッセージをお待ちしています", None
        return self._generate_function()

    def process_test(
        self, message: str
    ) -> Tuple[Optional[str | List[str]], Optional[str]]:
        yes_list = ["", "yes", "1", "true", "y", "はい", "そうです"]
        cleaned_message = message.strip()
        if cleaned_message.lower() in yes_list:
            next_step, next_type = self.get_nextstep()
            return f"テストをスキップします\n\n次のステップ: {next_step}", next_type
        return self._test_one_staffcode(cleaned_message)

    def process_work(
        self, message: str
    ) -> Tuple[Optional[str | List[str]], Optional[str]]:
        yes_list = ["", "yes", "1", "true", "y", "はい", "そうです"]
        if message not in yes_list:
            return "「Yes」のメッセージをお待ちしています", None
        return self._process_all_staffcodes()

    def process_revise(
        self, message: str
    ) -> Tuple[Optional[str | List[str]], Optional[str]]:
        skip_list = ["スキップ", "skip"]
        yes_list = ["", "yes", "1", "true", "y", "はい", "そうです"]
        if message in skip_list:
            return self.get_nextstep()
        if message not in yes_list:
            return "「Yes」のメッセージをお待ちしています", None
        return self._try_again()

    def process_continue(
        self, message: str
    ) -> Tuple[Optional[str | List[str]], Optional[str]]:
        yes_list = ["", "yes", "1", "true", "y", "はい", "そうです"]
        if message not in yes_list:
            return "「Yes」のメッセージをお待ちしています", None
        return f"次のタスク「{self.next_task_name}」に進みます", "next_task"

    def _process_message_normal_mode(
        self, message: str
    ) -> Tuple[Optional[str | List[str]], Optional[str]]:
        current_state = self.get_current_state()
        if current_state == "prepare":
            return self.process_prepare(message)
        elif current_state == "file":
            return self._process_file_message()
        elif current_state == "analysis":
            return self.process_analysis(message)
        elif current_state == "process":
            return self.process_generation(message)
        elif current_state == "test":
            return self.process_test(message)
        elif current_state == "work":
            return self.process_work(message)
        elif current_state == "revise":
            return self.process_revise(message)
        elif current_state == "continue":
            return self.process_continue(message)
        return "すべてのステップが完了しました。", "over"

    def process_message(
        self, message: str
    ) -> Tuple[Optional[str | List[str]], Optional[str]]:
        message_lower = message.lower().strip()
        no_list = ["no", "0", "false", "いいえ"]
        if message_lower in no_list:
            return "処理を終了します。", "early exit"
        if len(self.files) == 0:
            return "出力用のファイルの存在が必要です。処理終了します。", "early exit"
        if not self.fast_mode:
            return self._process_message_normal_mode(message)
        else:
            return self._process_message_fast_mode(message)

    def _process_message_fast_mode(
        self, message: str
    ) -> Tuple[Optional[str | List[str]], Optional[str]]:
        message_lower = message.lower().strip()
        no_list = ["no", "0", "false", "いいえ"]
        if message_lower in no_list:
            return "処理を終了します。", "early exit"
        current_state = self.get_current_state()
        if current_state == "prepare":
            return self.get_nextstep()
        elif current_state == "file":
            return self._process_file_message()
        elif current_state == "process":
            max_loop_times = 2
            attempts = 1
            while attempts <= max_loop_times:
                attempts += 1
                try:
                    self.code_agent._update_chain(
                        current_date=self.current_date, function_name=self.function_name
                    )
                    code_response = self.code_agent.execute(self.prompt_content)
                    with tempfile.NamedTemporaryFile(
                        suffix=".py", delete=False
                    ) as temp_file:
                        temp_file.write(code_response.encode())
                        temp_file_path = temp_file.name
                    spec = importlib.util.spec_from_file_location(
                        "temp_module", temp_file_path
                    )
                    temp_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(temp_module)
                    self.generated_func = getattr(temp_module, self.function_name)
                    results = []
                    errors = []
                    staff_codes = (
                        self.staff_codes.tolist()
                        if self.staff_codes is not None
                        else []
                    )
                    for staff_code in staff_codes:
                        try:
                            result = self.generated_func(
                                staff_code, self.code_agent.df_dict
                            )
                            if isinstance(result, pd.DataFrame):
                                results.append(result)
                            else:
                                errors.append(
                                    f"スタッフコード {staff_code}: 無効な戻り値"
                                )
                        except Exception as e:
                            errors.append(f"スタッフコード {staff_code}: {str(e)}")

                    os.remove(temp_file_path)
                    if results and (len(errors) == 0 or attempts > max_loop_times):
                        final_df = pd.concat(results, ignore_index=True)
                        save_msg = self.save_result_to_csv(final_df)
                        response = [
                            f"処理が完了しました。処理件数: {len(results)}, エラー件数: {len(errors)}",
                            f"エラー詳細:\n{chr(10).join(errors)}\n{save_msg}",
                        ]
                        self.state_machine.set_state("over")
                        return response, "over"
                    if not results and attempts > max_loop_times:
                        self.state_machine.set_state("over")
                        return [
                            "処理に失敗しました。結果がありません。",
                            "終了します。",
                        ], "early exit"
                except Exception as e:
                    if attempts > max_loop_times:
                        self.state_machine.set_state("over")
                        return [f"エラー: {str(e)}", "処理を終了します"], "early exit"
            return None, "over"
        return None, "over"

    @staticmethod
    def _process_df(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        if "スタッフコード" in df.columns:
            df.dropna(subset=["スタッフコード"], inplace=True)
            if pd.api.types.is_numeric_dtype(df["スタッフコード"]):
                df["スタッフコード"] = df["スタッフコード"].astype("int64")
            df["スタッフコード"] = df["スタッフコード"].astype("string")
        elif "社員番号" in df.columns:
            df["スタッフコード"] = df["社員番号"]
            df.dropna(subset=["スタッフコード"], inplace=True)
            if pd.api.types.is_numeric_dtype(df["スタッフコード"]):
                df["スタッフコード"] = (
                    df["スタッフコード"].astype("int64").astype("string")
                )
            else:
                df["スタッフコード"] = df["スタッフコード"].astype("string")
        else:
            raise ValueError("Both 'スタッフコード' and '社員番号' don't exist!")
        return df

    @staticmethod
    def _is_valid_date_format(date_string: str) -> bool:
        pattern = r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$"
        return bool(re.match(pattern, date_string))

    def _analysis_files(self) -> Tuple[List[str], Optional[str]]:
        try:
            analysis_prompt = "これらのファイルの列名の関係を日本語で分析してください。"
            chat_response = self.chat_agent.execute(analysis_prompt)

            files_info = []
            for file_name, file_id in self.file_ids.items():
                df = TaskAgent._process_df(self.file_agent.load_data_as_df(file_id))
                has_numeric = not df.select_dtypes(include=[np.number]).empty
                if not has_numeric:
                    df_html = df.describe(include=[np.number]).to_html()
                    files_info.append((file_name, df_html))

            with open(self._get_rule_file_path(), "r", encoding="utf-8") as f:
                self.prompt_content = f.read()

            next_step, next_type = self.get_nextstep()

            res = []
            res.append(f"全体の分析結果: \n {chat_response}")
            for file_name, df_html in files_info:
                res.append(f"{file_name}の分析結果:")
                res.append(df_html)
            res.append(f"次のステップ: {next_step}")

            return res, next_type

        except Exception as e:
            trace = traceback.format_exc()
            return [f"エラーが発生しました: {str(e)}\n{trace}"], "early exit"

    def _get_rule_file_path(self) -> str:
        base_path = os.getenv("LLM_EXCEL_BASE_PATH")
        rule_folder = os.path.join(base_path, "rule")
        return os.path.join(rule_folder, self.prompt_file)

    def _generate_function(self) -> Tuple[str, Optional[str]]:
        try:
            self.code_agent._update_chain(
                current_date=self.current_date, function_name=self.function_name
            )
            code_response = self.code_agent.execute(self.prompt_content)

            with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as temp_file:
                temp_file.write(code_response.encode())
                temp_file_path = temp_file.name

            spec = importlib.util.spec_from_file_location("temp_module", temp_file_path)
            temp_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(temp_module)
            self.generated_func = getattr(temp_module, self.function_name)

            next_step, next_type = self.get_nextstep()
            return f"処理の準備が完了しました。\n\n次のステップ: {next_step}", next_type

        except Exception as e:
            trace = traceback.format_exc()
            self.state_machine.set_state("over")
            return f"エラーが発生しました: {str(e)}\n{trace}", "early exit"

    def _test_one_staffcode(self, cleaned_message: str) -> Tuple[str, Optional[str]]:
        if not re.match(r"^\d+$", cleaned_message):
            return "有効な「スタッフコード」または「Yes」を入力してください", None

        try:
            result = self.generated_func(cleaned_message, self.code_agent.df_dict)
            next_step, next_type = self.get_nextstep()
            return f"テスト結果:\n{result}\n\n次のステップ: {next_step}", next_type
        except Exception as e:
            self.state_machine.set_state("over")
            return f"テスト実行中にエラーが発生しました: {str(e)}", "early exit"

    def _process_all_staffcodes(self) -> Tuple[str, Optional[str]]:
        if self.staff_codes is None:
            return "「スタッフコード」の取得に失敗しました。", None
        try:
            results = []
            errors = []
            for staff_code in self.staff_codes:
                try:
                    tmp_df = self.generated_func(staff_code, self.code_agent.df_dict)
                    if isinstance(tmp_df, pd.DataFrame):
                        results.append(tmp_df)
                    else:
                        errors.append(f"スタッフコード {staff_code}: 無効な戻り値")
                except Exception as e:
                    errors.append(f"スタッフコード {staff_code}: {str(e)}")

            if results:
                final_df = pd.concat(results, ignore_index=True)
                save_msg = self.save_result_to_csv(final_df)
                res = [
                    f"処理が完了しました。\n処理件数: {len(results)}\nエラー件数: {len(errors)}",
                    f"エラー詳細:\n{chr(10).join(errors)}\n{save_msg}",
                ]
                if len(errors) != 0:
                    next_step, next_type = self.get_nextstep()
                    res.append(next_step)
                    return res, next_type
                else:
                    self.get_nextstep()
                    next_step, next_type = self.get_nextstep()
                    res.append(next_step)
                    return res, next_type
            else:
                next_step, next_type = self.get_nextstep()
                return [
                    "処理に失敗しました。データの処理結果がありません。",
                    next_step,
                ], next_type

        except Exception:
            trace = traceback.format_exc()
            next_step, next_type = self.get_nextstep()
            return [
                f"データ処理中にエラーが発生しました。\n{trace}",
                next_step,
            ], next_type

    def _try_again(self) -> Tuple[str, Optional[str]]:
        try:
            code_response = self.code_agent.execute(self.prompt_content)
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as temp_file:
                temp_file.write(code_response.encode())
                temp_file_path = temp_file.name

            spec = importlib.util.spec_from_file_location("temp_module", temp_file_path)
            temp_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(temp_module)
            self.generated_func = getattr(temp_module, self.function_name)

            results = []
            errors = []

            for staff_code in self.staff_codes:
                try:
                    tmp_df = self.generated_func(staff_code, self.code_agent.df_dict)
                    if isinstance(tmp_df, pd.DataFrame):
                        results.append(tmp_df)
                    else:
                        errors.append(f"スタッフコード {staff_code}: 無効な戻り値")
                except Exception as e:
                    errors.append(f"スタッフコード {staff_code}: {str(e)}")

            if results:
                final_df = pd.concat(results, ignore_index=True)
                save_msg = self.save_result_to_csv(final_df)
                res = [
                    f"処理が完了。処理件数: {len(results)}, エラー件数: {len(errors)}",
                    f"エラー詳細:\n{chr(10).join(errors)}\n{save_msg}",
                ]
                if len(errors) != 0:
                    current_step, current_type = self.get_currentstep()
                    res.append(current_step)
                    return "\n".join(res), current_type
                else:
                    next_step, next_type = self.get_nextstep()
                    res.append(next_step)
                    return "\n".join(res), next_type
            else:
                current_step, current_type = self.get_currentstep()
                return (
                    f"処理に失敗しました。データの処理結果がありません。\n{current_step}",
                    current_type,
                )

        except Exception as e:
            current_step, current_type = self.get_currentstep()
            return (
                f"データ処理中にエラーが発生しました: {str(e)}\n\n{current_step}",
                current_type,
            )

    def _process_file_message(self) -> Tuple[str, Optional[str]]:
        try:
            total_files = self.file_num + len(self.files_optional)
            for cur_idx in range(total_files):
                current_file = (
                    self.files[cur_idx]
                    if cur_idx < self.file_num
                    else self.files_optional[cur_idx - self.file_num]
                )
                df = self.file_agent.load_data_as_df_by_definition(current_file["定義"])
                self.code_agent.add_dataframe(df, current_file["ファイル名前"])
                self.chat_agent.add_dataframe(df, current_file["ファイル名前"])

                if current_file.get("出力用", False):
                    if self.staff_codes is not None:
                        self.state_machine.set_state("over")
                        return (
                            "複数のファイルが同時に出力用となっていますが、1つのみが想定されています。処理終了します。",
                            "over",
                        )
                    self.staff_codes = df["スタッフコード"].copy()

            if self.fast_mode:
                with open(self._get_rule_file_path(), "r", encoding="utf-8") as f:
                    self.prompt_content = f.read()

            next_step, next_type = self.get_nextstep()
            return f"ファイルチェック完了。\n次のステップ: {next_step}", next_type

        except Exception as e:
            self.state_machine.set_state("over")
            return f"エラー: {str(e)}。\n処理を終了します。", "early exit"

    def save_result_to_csv(self, result: pd.DataFrame) -> str:
        base_path = os.getenv("LLM_EXCEL_BASE_PATH")
        output_dir = os.path.join(base_path, "output")
        os.makedirs(output_dir, exist_ok=True)

        file_name = f"{self.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path = os.path.join(output_dir, file_name)
        try:
            result.to_csv(file_path, index=False, encoding="utf-8-sig")
            if self.next_task_replaced_file_definition is not None:
                self.file_agent.store_csv_file(
                    result,
                    self.next_task_replaced_file_name,
                    file_path,
                    file_name,
                    self.next_task_replaced_file_definition,
                    self.next_task_name,
                    self.next_task_replaced_file_output_usage,
                )
            self.saved_file_path = file_path
            return f"結果を {file_path} に保存しました。"
        except Exception as e:
            self.state_machine.set_state("over")
            return f"ファイル保存中にエラー: {str(e)}"

    def reset(self):
        self.file_state.reset()
        self.state_machine.set_state("prepare")
        self.results.clear()
        self.file_ids.clear()
        self.code_agent = CodeAgent(self.llm_code)
        self.chat_agent = ChatAgent(self.llm_chat)
        self.generated_func = None
        self.staff_codes = None
        self.prompt_content = None
        self.replaced_file_name = None
        self.replaced_file_path = None

    def _create_df_from_user_file(
        self, file_path: str, current_file: dict
    ) -> Tuple[pd.DataFrame, Optional[str]]:
        """
        AgentCollection側から呼ばれる:
        file_path と current_file 情報を使って FileAgent のチェックを経て DataFrame を生成する。
        """
        return self.file_agent._create_df_from_file(
            file_path=file_path,
            folder_name=self.name,
            current_file_name=current_file["ファイル名前"],
        )
