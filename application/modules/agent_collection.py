import json
import logging
import os
import traceback
from collections import deque
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union, Any

from transitions import Machine

# Azure Open AI 用のラッパーをインポート
from application.modules.azure_openai_wrapper import AzureOpenAIWrapper
from application.modules.file_agent import FileAgent
from application.modules.intent_analyzer import IntentAnalyzer
from application.modules.rag_agent import RAG_Agent
from application.modules.task_agent import TaskAgent
from application.modules.utils import return_most_similiar_word


class IntentType(Enum):
    TASK_START = "task_start"
    QUESTION = "question"
    FILE_UPLOAD = "file_upload"
    CONFIRMATION = "confirmation"
    RETURN_TO_MENU = "return_to_menu"
    UNKNOWN = "unknown"


class AgentCollection:
    """
    エージェント（FileAgent, TaskAgent, RAG_Agentなど）の統合管理。
    ユーザー入力の意図解析と、その結果に基づく処理振り分けを行う。
    """

    def __init__(self, config_path: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.logger.info("エージェントコレクションを初期化しています...")

        self.file_agent = FileAgent()
        self.logger.info("ファイルエージェントを初期化しました。")

        self.task_agents: Dict[str, TaskAgent] = {}
        self.task_info_dict = {}
        self.current_task = None
        self.config_path = config_path

        # Azure Open AI の API キー、バージョン、エンドポイントはラッパー内にハードコード済み
        # モデル名は必要に応じて設定してください（例："gpt-model-name"）
        self.llm_code = AzureOpenAIWrapper(model="gptest", temperature=0)
        self.llm_chat = AzureOpenAIWrapper(model="gptest", temperature=0)
        self.llm_analyzer = AzureOpenAIWrapper(model="gptest", temperature=0)

        self.load_config()
        self.logger.info("IntentAnalyzer を初期化")
        self.intent_analyzer = IntentAnalyzer(llm=self.llm_analyzer)

        self.logger.info("RAG_AGENT: 初期化開始")
        self.rag_agent = RAG_Agent(llm=self.llm_chat)
        self.logger.info("RAG_AGENT: 初期化完了")

        self.logger.info("workflow 作成")
        self.workflow: deque[str] = deque()

        # 状態マシン（chat, file, task, date）
        states = ["chat", "file", "task", "date"]
        self.state_machine = Machine(states=states, initial="chat")

    def load_config(self) -> None:
        """config.jsonを読み込み、タスク設定を保持する"""
        try:
            if not os.path.exists(self.config_path):
                self.logger.error(f"設定ファイルが見つかりません: {self.config_path}")
                raise FileNotFoundError(
                    f"設定ファイルが見つかりません: {self.config_path}\n"
                    "CONFIG_PATH環境変数を設定するか、デフォルトの位置にconfig.jsonを配置してください。"
                )
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                for task in config["タスク"]:
                    self.task_info_dict[task["名称"]] = task

            self.logger.info(f"設定ファイルを正常に読み込みました: {self.config_path}")
            self.file_agent.task_configs = self.task_info_dict
            self._create_task_agents()

        except FileNotFoundError as e:
            self.logger.error(f"エラー: {str(e)}")
        except json.JSONDecodeError:
            self.logger.error(
                f"エラー: {self.config_path} の解析に失敗しました。JSONの形式を確認してください。"
            )
        except Exception as e:
            self.logger.error(f"設定ファイルの読み込み中に予期せぬエラー: {str(e)}")
            traceback.print_exc()

    def _create_task_agents(self) -> None:
        """各TaskAgentを設定情報から生成"""
        idx = 0
        for task_config in self.file_agent.task_configs.values():
            task = TaskAgent(
                task_config,
                self.file_agent,
                llm_code=self.llm_code,
                llm_chat=self.llm_chat,
                idx=idx,
            )
            idx += 1
            self.task_agents[task.name] = task

        if self.task_agents:
            self.logger.info(f"タスクを正常に作成。タスク数: {len(self.task_agents)}")
        else:
            self.logger.warning(
                "警告: タスクが作成されませんでした。config.jsonを確認してください。"
            )

    def get_current_state(self) -> str:
        return self.state_machine.state

    def set_state(self, state: str):
        self.logger.info(f"状態を変更: {self.get_current_state()} -> {state}")
        self.state_machine.set_state(state)

    def set_task_speed_mode(self):
        if len(self.workflow) > 1:
            for task_name in list(self.workflow):
                self.task_agents[task_name].set_fast_mode()
        else:
            for task_name in list(self.workflow):
                self.task_agents[task_name].set_normal_mode()

    def process_message(self, message: str) -> Tuple[Union[str, List[str]], str]:
        """Process a user message and return a response"""
        current_state = self.get_current_state()
        
        try:
            if current_state == "date":
                return self._process_date_message(message)
            
            if current_state == "task":
                if self.current_task is not None:
                    result = self.current_task.process_message(message)
                    # Ensure we're returning a tuple
                    if isinstance(result, tuple) and len(result) == 2:
                        return result
                    else:
                        # Convert to expected format if not already a tuple
                        return result, ""
                else:
                    return "エラー: タスクの選択に失敗しました。", ""
            
            # For all other states, analyze intent and route
            try:
                intent_response = self.intent_analyzer(message, task_info=self.task_info_dict)
                return self.route_intent(intent_response, message)
            except Exception as e:
                self.logger.error(f"Error analyzing intent: {str(e)}")
                return f"メッセージの処理中にエラーが発生しました: {str(e)}", "error"
                
        except Exception as e:
            self.logger.error(f"Error in process_message: {str(e)}")
            self.logger.exception("Detailed traceback:")
            return f"処理中にエラーが発生しました: {str(e)}", "error"

    def analyze_intent(self, message: str) -> Dict:
        response = self.intent_analyzer(message, task_info=self.task_info_dict)
        return response

    def route_intent(
        self, intent_response: Dict, message: str
    ) -> Tuple[Optional[str | List[str]], Optional[str]]:
        intent_str = intent_response.get("intent", "unknown")
        try:
            intent = IntentType(intent_str)
        except ValueError:
            intent = IntentType.UNKNOWN
        
        # Prepare default response format
        response_text = None
        extra_info = ""
        
        try:
            if intent == IntentType.RETURN_TO_MENU:
                self.set_state("chat")
                response_text = "メニューにかえりました。給与計算に関して何か手伝い欲しいことがありますか"
            
            elif intent == IntentType.CONFIRMATION:
                if self.get_current_state() == "task" and self.current_task is not None:
                    result = self.current_task.process_message(message)
                    # Extract response_text and extra_info if result is a tuple
                    if isinstance(result, tuple) and len(result) == 2:
                        response_text, extra_info = result
                    else:
                        response_text = result
                        extra_info = ""
                else:
                    response_text = "現在、確認を必要とするタスクはありません。新しいチャットを開始してください。"
            
            elif intent == IntentType.TASK_START:
                info = self.parse_task_names(intent_response)
                response_text = info
                extra_info = "selection"
            
            elif intent == IntentType.FILE_UPLOAD:
                if self.get_current_state() == "file":
                    result = self._process_file_message(message)
                    if isinstance(result, tuple) and len(result) == 2:
                        response_text, extra_info = result
                    else:
                        response_text = result
                        extra_info = ""
                elif self.get_current_state() == "chat":
                    file_path = message.replace("選択されたファイル: ", "").strip()
                    response_text = self.file_agent.check_file_identity(file_path)
                    extra_info = ""
            
            elif intent == IntentType.QUESTION:
                result = self._process_question(message)
                if isinstance(result, tuple) and len(result) == 2:
                    response_text, extra_info = result
                else:
                    response_text = result
                    extra_info = ""
            
            else:
                response_text = "あなたの意図がわからないんです。もう一回聞いてください。"
        
        except Exception as e:
            self.logger.error(f"Error in route_intent: {str(e)}")
            self.logger.exception("Detailed traceback:")
            response_text = f"処理中にエラーが発生しました: {str(e)}"
            extra_info = "error"
        
        # Ensure we're returning a tuple with the correct types
        if response_text is None:
            response_text = "応答が生成されませんでした。"
        
        return response_text, extra_info

    def _process_question(self, msg: str) -> Tuple[str, Optional[str]]:
        resp = self.rag_agent.execute(msg)
        return resp, ""

    def _process_date_message(self, message: str) -> Tuple[str, Optional[str]]:
        message_lower = message.lower()
        if not TaskAgent._is_valid_date_format(message_lower):
            return "日付形式をチェックして、もう一回入力してください。", ""
        for task in self.task_agents.values():
            task.current_date = message_lower
        return (
            f"現在日付は「{message_lower}」です。\nタスクの処理は開始します。",
            "switch task",
        )

    def _process_file_message(
        self, message: str
    ) -> Tuple[Optional[List[str]], Optional[str]]:
        file_path = message.replace("選択されたファイル: ", "").strip()
        shared_msg = "もう一回アップロードしてください。"
        if not os.path.isfile(file_path):
            return f"無効なファイルパスです。{shared_msg}", ""
        if not (
            file_path.lower().endswith(".csv") or file_path.lower().endswith(".xlsx")
        ):
            return f"EXCELとCSVファイルのみ受け付けます。{shared_msg}", ""
        try:
            current_file = self.needed_file_list[self.cur_file_idx]
            current_task_for_file = self.task_agents[current_file["名称"]]
            df, check_info = current_task_for_file._create_df_from_user_file(
                file_path=file_path, current_file=current_file
            )
            if df is None:
                info_list = [
                    "ファイルロード失敗しました。以下は不一致するところの情報です："
                ]
                if isinstance(check_info, list):
                    info_list.extend(check_info)
                else:
                    info_list.append(check_info)
                info_list.append(shared_msg)
                return info_list, ""
            df = TaskAgent._process_df(df)
            self.file_agent.store_csv_file(
                df,
                current_file["ファイル名前"],
                file_path,
                os.path.basename(file_path),
                current_file["定義"],
                current_task_for_file.name,
                current_file["出力用"],
            )
            self.cur_file_idx += 1
            while self.cur_file_idx < len(self.needed_file_list):
                next_file = self.needed_file_list[self.cur_file_idx]
                if (
                    self.file_agent.check_file_uploaded_by_definition(next_file["定義"])
                    or next_file["定義"] in self.reused_output_file_set
                ):
                    self.cur_file_idx += 1
                else:
                    break
            if self.cur_file_idx == len(self.needed_file_list):
                from datetime import date

                current_date = date.today().strftime("%Y-%m-%d")
                self.set_state("date")
                return self._process_date_message(current_date)

            else:
                next_def = self.needed_file_list[self.cur_file_idx]["定義"]
                return (
                    f"ファイルを保存しました。\nファイル「{next_def}」をアップロードしてください。",
                    "",
                )
        except Exception as e:
            self.set_state("chat")
            self.logger.exception("ファイル処理中にエラーが発生しました。")
            return f"エラー: {str(e)}", ""

    def process_files(self) -> Tuple[Optional[List[str]], Optional[str]]:
        """Collect and process files needed for the current task"""
        current_state = self.get_current_state()
        if current_state != "file":
            self.set_state("file")
        self._collect_all_needed_files()

        # Check if needed_file_list is empty before accessing elements
        if not self.needed_file_list:
            return ["このタスクには必要なファイルがありません。設定を確認してください。"], "no_files"

        # Ensure cur_file_idx is valid
        if self.cur_file_idx >= len(self.needed_file_list):
            self.cur_file_idx = 0

        # Make sure needed_file_list[self.cur_file_idx] has the required key
        if len(self.needed_file_list) > 0 and '定義' not in self.needed_file_list[self.cur_file_idx]:
            return ["ファイル定義の設定に問題があります。管理者に連絡してください。"], "file_definition_error"

        response_1 = "今から必要なファイルをアップロードしましょう。"
        response_2 = f"ファイル「{self.needed_file_list[self.cur_file_idx]['定義']}」をアップロードしてください。"
        return [response_1, response_2], ""

    def _collect_all_needed_files(self) -> None:
        """Collect all files needed for tasks in the workflow"""
        self.needed_file_list = []
        self.reused_output_file_set = set()

        # Debug log the workflow and task agents
        self.logger.info(f"Collecting files for workflow: {list(self.workflow)}")
        self.logger.info(f"Available task agents: {list(self.task_agents.keys())}")

        for task_name in list(self.workflow):
            # Make sure task_name is in task_agents
            if task_name not in self.task_agents:
                self.logger.warning(f"Task {task_name} not found in task_agents")
                continue
                
            task_agent = self.task_agents[task_name]
            
            # Check if task has files defined
            if not hasattr(task_agent, 'files') or not task_agent.files:
                self.logger.warning(f"Task {task_name} has no files defined")
                
            # Add required files
            for file in getattr(task_agent, 'files', []):
                # Make sure file is a dict and has the required keys
                if not isinstance(file, dict):
                    self.logger.warning(f"File in task {task_name} is not a dict: {file}")
                    continue
                    
                if '名称' not in file:
                    file["名称"] = task_agent.name
                self.needed_file_list.append(file)
                
            # Add optional files
            for file in getattr(task_agent, 'files_optional', []):
                if not isinstance(file, dict):
                    continue
                    
                if '名称' not in file:
                    file["名称"] = task_agent.name
                self.needed_file_list.append(file)
                
            # Handle next task replaced file
            next_def = getattr(task_agent, 'next_task_replaced_file_definition', None)
            if next_def:
                self.reused_output_file_set.add(next_def)

        # Report the results
        self.logger.info(f"Collected {len(self.needed_file_list)} needed files and {len(self.reused_output_file_set)} reused files")
        
        # Reset file index
        self.cur_file_idx = 0
        
        # If we have no needed files, add a message
        if not self.needed_file_list:
            self.logger.warning("No needed files found for the current workflow")

    def get_task_list(self) -> List[str]:
        return list(self.task_agents.keys())

    def get_task(self, task_name: str) -> Optional[TaskAgent]:
        return self.task_agents.get(task_name)

    def is_mgr_mode(self) -> bool:
        return self.get_current_state() != "task"

    def set_task_mode(self) -> None:
        self.set_state("task")

    def set_mgr_mode(self) -> None:
        self.set_state("chat")

    def reset_all_task_agents(self):
        for task_name in self.task_agents.keys():
            self.reset_task(task_name)
        self.current_task = None
        self.set_state("chat")

    def set_current_task_agent(self, task_name: str) -> bool:
        self.logger.info(f"現在タスクを変更: {task_name}")
        task = self.get_task(task_name)
        if task:
            self.current_task = task
            self.set_state("chat")
            return True
        self.logger.warning("存在しないタスクが指定されました。")
        return False

    def get_current_task_agent(self) -> Optional[TaskAgent]:
        return self.current_task

    def get_task_description(self, task_name: str) -> str:
        task = self.get_task(task_name)
        return task.get_description() if task else "タスクが見つかりません。"

    def get_task_files(self, task_name: str) -> List[str]:
        task = self.get_task(task_name)
        return task.get_files() if task else []

    def get_next_step(self, task_name: str) -> Tuple[Optional[str], Optional[str]]:
        task = self.get_task(task_name)
        if task:
            return task.get_nextstep()
        return None, None

    def reset_task(self, task_name: str):
        self.logger.info(f"タスク {task_name} をリセットします。")
        task = self.get_task(task_name)
        if task:
            task.reset()

    def get_stored_files(self, task_name: str = None) -> List[Dict]:
        files = (
            self.file_agent.get_files_by_task(task_name)
            if task_name
            else self.file_agent.get_file_info()
        )
        return [
            {
                "id": f.id,
                "name": f.original_name,
                "task": f.task_name,
                "upload_date": f.upload_date.strftime("%Y-%m-%d %H:%M:%S"),
                "row_count": f.row_count,
                "output": f.output,
            }
            for f in files
        ]

    def get_all_stored_files(self) -> List[Dict]:
        files = self.file_agent.get_all_files()
        return [
            {
                "id": f.id,
                "name": f.original_name,
                "task": f.task_name,
                "upload_date": f.upload_date.strftime("%Y-%m-%d %H:%M:%S"),
                "row_count": f.row_count,
                "output": f.output,
            }
            for f in files
        ]

    def get_grouped_tasks(self) -> dict:
        grouped = {}
        for task in self.task_agents.values():
            group_name = (
                task.name.split("(")[0].strip() if "(" in task.name else task.name
            )
            grouped.setdefault(group_name, []).append(task)
        return grouped

    def delete_task_files(self, task_name: str):
        try:
            files = self.file_agent.get_files_by_task(task_name)
            for file in files:
                self.file_agent.delete_file(file.id)
            self.logger.info(f"タスク '{task_name}' の全ファイルを削除しました。")
        except Exception as e:
            self.logger.error(f"ファイル削除中にエラーが発生しました: {str(e)}")

    def cleanup_old_files(self, days: int = 30):
        try:
            all_files = self.file_agent.get_file_info()
            current_time = datetime.now()
            for file in all_files:
                if (current_time - file.upload_date).days > days:
                    self.file_agent.delete_file(file.id)
            self.logger.info(f"{days}日より古いファイルを削除しました。")
        except Exception as e:
            self.logger.error(f"古いファイルの削除中にエラーが発生しました: {str(e)}")
