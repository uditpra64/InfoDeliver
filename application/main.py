import datetime
import logging
import os
import sys
import threading
from functools import partial

from dotenv import load_dotenv
from PIL import Image
from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFontMetrics, QImage, QKeyEvent, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# --- インポート ---
from modules.agent_collection import AgentCollection
from modules.task_agent import TaskAgent


def setup_logging():
    """アプリケーション用のロギング設定"""
    if not os.path.exists("log"):
        os.makedirs("log")
    log_filename = datetime.datetime.now().strftime("log/log_%Y%m%d_%H%M%S.log")
    logging.basicConfig(
        filename=log_filename,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        encoding="utf-8",
    )
    logger = logging.getLogger(__name__)
    return logger


logger = setup_logging()
load_dotenv()

# アイコンファイルの取得と存在チェック
icon_file = os.getenv("ICON_FILE", "icon.png")
if not os.path.exists(icon_file):
    logger.error(f"アイコンファイル {icon_file} が見つかりません．")
    raise FileNotFoundError(f"アイコンファイル {icon_file} が見つかりません．")

# PILで画像読み込み、RGBA変換後にQImageへ変換
pil_image = Image.open(icon_file)
if pil_image.mode != "RGBA":
    pil_image = pil_image.convert("RGBA")
q_image = QImage(
    pil_image.tobytes(),
    pil_image.width,
    pil_image.height,
    QImage.Format.Format_RGBA8888,
)


class ChatBubbleWidget(QWidget):
    """
    チャットバブル表示ウィジェット。ユーザー／ボットで色や配置を変更する。
    """

    def __init__(self, message, is_user=True, is_html=False):
        super().__init__()

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        if not is_user:
            icon_label = QLabel()
            icon_pixmap = QPixmap(q_image).scaled(
                30,
                30,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            icon_label.setPixmap(icon_pixmap)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignLeft)

        if not is_html:
            label = (
                QLabel(message)
                if not isinstance(message, tuple)
                else QLabel(message[0])
            )
            label.setWordWrap(True)
        else:
            if isinstance(message, tuple):
                message = message[0]
            message_html = (
                f"<html><head>{self.get_styles()}</head><body>{message}</body></html>"
            )
            label = QLabel()
            label.setText(message_html)
            label.setWordWrap(True)
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setWidget(label)

        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        if is_user:
            label.setStyleSheet(
                """
                QLabel {
                    background-color: #e5e5ea;
                    border-radius: 25px;
                    padding: 8px;
                    color: black;
                    font-size: 16px;
                }
                """
            )
            layout.addStretch()
            if not is_html:
                layout.addWidget(label)
            else:
                layout.addWidget(scroll_area)
        else:
            if not is_html:
                label.setStyleSheet(
                    """
                    QLabel {
                        background-color: #c4c4c4;
                        border-radius: 25px;
                        padding: 8px;
                        color: black;
                        font-size: 16px;
                    }
                    """
                )
                layout.addWidget(label)
            else:
                label.setStyleSheet(
                    """
                    QLabel {
                        background-color: #c4c4c4;
                        border-radius: 20px;
                        padding: 8px;
                        color: black;
                    }
                    """
                )
                layout.addWidget(scroll_area)
            layout.addStretch()

        self.setLayout(layout)
        self.label = label

    def get_styles(self):
        """HTMLテーブル用のCSSスタイル"""
        return """
        <style>
            .dataframe {
                font-family: Arial, sans-serif;
                border-collapse: collapse;
                width: 100%;
            }
            .dataframe th, .dataframe td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            .dataframe th {
                background-color: #f2f2f2;
                font-weight: bold;
            }
            .dataframe tr:nth-child(even) {
                background-color: #f9f9f9;
            }
            .dataframe tr:hover {
                background-color: #f1f1f1;
            }
        </style>
        """


class CustomLineEdit(QLineEdit):
    """
    Enterキーでテキスト送信するQLineEditの拡張。
    """

    returnPressed = pyqtSignal(str)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
            self.returnPressed.emit(self.text())
            self.clear()
        else:
            super().keyPressEvent(event)


class MgrMessageWorker(QObject):
    """
    バックグラウンドでAgentCollectionの処理を実行するワーカー。
    """

    finished = pyqtSignal()
    response = pyqtSignal(str, str)
    task_response = pyqtSignal(str, bool)
    agent_signal = pyqtSignal("PyQt_PyObject", str)
    operation_signal = pyqtSignal(str, TaskAgent)
    process_file_signal = pyqtSignal("PyQt_PyObject")
    debug_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()

    def process_message(self, agent_collection: AgentCollection, message: str):
        logger = logging.getLogger(__name__)
        try:
            response, extra_info = agent_collection.process_message(message)
            current_state = agent_collection.get_current_state()
            if current_state != "task":
                if not isinstance(response, list):
                    self.response.emit(response, extra_info)
                else:
                    for i, resp_text in enumerate(response):
                        if i == len(response) - 1:
                            self.response.emit(resp_text, extra_info)
                        else:
                            self.response.emit(resp_text, "")
            else:
                if not isinstance(response, list):
                    self.task_response.emit(response, False)
                else:
                    for res in response:
                        self.task_response.emit(res, False)
                self.operation_signal.emit(extra_info, agent_collection.current_task)
        finally:
            if agent_collection.get_current_state() != "task":
                self.finished.emit()
            else:
                if (
                    agent_collection.current_task is not None
                    and not agent_collection.current_task.is_fast_mode()
                ):
                    self.finished.emit()
                else:
                    if extra_info in ["early exit", "over"]:
                        self.finished.emit()

    def start_file_process(self, agent_collection: AgentCollection):
        logger = logging.getLogger(__name__)
        response, extra_info = agent_collection.process_files()
        if not isinstance(response, list):
            self.response.emit(response, extra_info)
        else:
            for res in response:
                self.response.emit(res, extra_info)


class ChatGPTApp(QMainWindow):
    """
    メインウィンドウ。タスク一覧／ファイル一覧／チャット表示などを構築。
    """

    mgr_message_signal = pyqtSignal(AgentCollection, str)
    start_file_process_signal = pyqtSignal(AgentCollection)

    def __init__(self, agent_collection: AgentCollection):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.agent_collection = agent_collection
        self.chat_history = []
        self.current_chat = []
        self.chain_mutex = threading.Lock()

        self.init_ui()
        self._create_mgr_thread()

    def init_ui(self):
        self.setWindowTitle("給与計算アプリ")
        self.setGeometry(100, 100, 1200, 800)

        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)

        # 左ペイン
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        self._set_task_table(left_layout)
        self._setup_file_table(left_layout)
        self._setup_history_list(left_layout)

        # 右ペイン
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        self._setup_chat_display(right_layout)
        self._setup_input_area(right_layout)
        self._setup_new_chat_button(right_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        main_layout.addWidget(splitter)
        self.setCentralWidget(main_widget)

        self._initialize_chat()
        self.update_file_table()
        self.update_task_table()

    def _setup_file_table(self, layout: QVBoxLayout):
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(5)
        self.file_table.setHorizontalHeaderLabels(
            ["ファイル名", "タスク", "アップロード日時", "行数", "出力用"]
        )
        self.file_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.file_table_title = QLabel("ファイル一覧")
        layout.addWidget(self.file_table_title)
        layout.addWidget(self.file_table)
        self.file_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

    def _set_task_table(self, layout: QVBoxLayout):
        self.task_table = QTableWidget()
        self.task_table.setColumnCount(2)
        self.task_table.setHorizontalHeaderLabels(["名称", "概要"])
        self.task_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.task_table_title = QLabel("タスク一覧")
        layout.addWidget(self.task_table_title)
        layout.addWidget(self.task_table)
        self.task_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.task_table.cellClicked.connect(self._on_cell_click)

    def _setup_history_list(self, layout: QVBoxLayout):
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.load_history_chat)
        self.history_list_title = QLabel("チャット履歴")
        layout.addWidget(self.history_list_title)
        layout.addWidget(self.history_list)

    def _setup_chat_display(self, layout: QVBoxLayout):
        self.chat_display = QListWidget()
        layout.addWidget(self.chat_display)

    def _setup_input_area(self, layout: QVBoxLayout):
        input_layout = QHBoxLayout()
        self.file_upload_button = QPushButton("ファイル")
        self.file_upload_button.clicked.connect(self.select_multiple_files)
        font_metrics = QFontMetrics(self.file_upload_button.font())
        width = font_metrics.horizontalAdvance("ファイル") + 20
        self.file_upload_button.setFixedWidth(width)
        input_layout.addWidget(self.file_upload_button)

        self.user_input = CustomLineEdit()
        self.user_input.setPlaceholderText("メッセージを入力してください...")
        self.user_input.returnPressed.connect(self.send_message)
        self.user_input.setReadOnly(False)
        input_layout.addWidget(self.user_input)

        layout.addLayout(input_layout)

    def _setup_new_chat_button(self, layout: QVBoxLayout):
        self.new_chat_button = QPushButton("新しいチャット")
        self.new_chat_button.clicked.connect(self.start_new_chat)
        layout.addWidget(self.new_chat_button)

    def _create_mgr_thread(self):
        self.mgr_thread = QThread()
        self.mgr_worker = MgrMessageWorker()
        self.mgr_worker.moveToThread(self.mgr_thread)
        self.mgr_thread.finished.connect(self.mgr_thread.deleteLater)

        self.mgr_worker.agent_signal.connect(
            self.mgr_worker.process_message, Qt.ConnectionType.QueuedConnection
        )
        self.mgr_message_signal.connect(self.mgr_worker.agent_signal)
        set_write_ok = partial(
            lambda flag: self.user_input.setReadOnly(flag), flag=False
        )
        self.mgr_worker.finished.connect(set_write_ok)

        self.mgr_worker.process_file_signal.connect(
            self.mgr_worker.start_file_process, Qt.ConnectionType.QueuedConnection
        )
        self.start_file_process_signal.connect(self.mgr_worker.process_file_signal)

        self.mgr_worker.operation_signal.connect(self._process_task_operation_signal)
        self.mgr_worker.response.connect(self._process_agent_collection_response)
        self.mgr_worker.task_response.connect(self._process_task_response)
        self.mgr_worker.debug_signal.connect(self.logger.debug)

        self.mgr_thread.start()

    def update_file_table(self):
        files = self.agent_collection.get_all_stored_files()
        self.file_table.setRowCount(len(files))
        for i, file in enumerate(files):
            self.file_table.setItem(i, 0, QTableWidgetItem(file["name"]))
            self.file_table.setItem(i, 1, QTableWidgetItem(file["task"]))
            self.file_table.setItem(i, 2, QTableWidgetItem(file["upload_date"]))
            self.file_table.setItem(i, 3, QTableWidgetItem(str(file["row_count"])))
            self.file_table.setItem(i, 4, QTableWidgetItem(str(file["output"])))
        self.file_table.resizeColumnsToContents()

    def update_task_table(self):
        grouped_tasks = self.agent_collection.get_grouped_tasks()
        self.task_table.setRowCount(len(grouped_tasks))
        for i, (group_name, tasks) in enumerate(grouped_tasks.items()):
            # 複数タスクの場合は説明を連結するなど工夫する
            description = " / ".join(task.description for task in tasks)
            self.task_table.setItem(i, 0, QTableWidgetItem(group_name))
            self.task_table.setItem(i, 1, QTableWidgetItem(description))
        self.task_table.resizeColumnsToContents()

    def _on_cell_click(self, row, column):
        item = self.task_table.item(row, 0)
        if not item:
            return
        group_name = item.text()
        grouped_tasks = self.agent_collection.get_grouped_tasks()
        if group_name not in grouped_tasks:
            self._add_chat_bubble("エラー: グループの取得に失敗しました。")
            return

        # 既にタスクが実行中の場合は注意を促す
        if not self.agent_collection.is_mgr_mode():
            self._add_chat_bubble(
                "タスクの処理中ですから、「新しいチャット」のボタンをクリックしてください。"
            )
            return

        # UI上はグループ名だけを表示しているが、裏ではグループ内の全タスクを順に実行する
        tasks_in_group = grouped_tasks[group_name]
        # ワークフローにタスク名を順番に追加（例えばconfig.jsonに記載順にするならtasks_in_groupのリスト順）
        for task in tasks_in_group:
            self.agent_collection.workflow.append(task.name)
        # 最初のタスクを選択して実行開始
        self.on_task_selected(tasks_in_group[0].name)

    def select_multiple_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "EXCELまたはCSVファイルを選択してください",
            "",
            "Excel or CSV Files (*.xlsx *.csv);;All Files (*)",
        )
        if not files:
            return
        for file in files:
            self.send_message(f"選択されたファイル: {file}")
        self.update_file_table()

    def send_message(self, message: str):
        self.logger.info(f"User sends message: {message}")
        self.user_input.setReadOnly(True)
        if self.agent_collection.is_mgr_mode():
            self._add_chat_bubble(message)
            if self.agent_collection.get_current_state() == "chat":
                self._add_chat_bubble("生成中....", False, False)
            self.mgr_message_signal.emit(self.agent_collection, message)
        else:
            if message == "":
                message = "yes"
            self._add_chat_bubble(message)
            self.mgr_message_signal.emit(self.agent_collection, message)

    def send_message_simple_version(self, agent_collection: AgentCollection, msg: str):
        self.logger.info(f"Simple send message: {msg}")
        self.user_input.setReadOnly(True)
        self.mgr_message_signal.emit(agent_collection, msg)

    def _process_agent_collection_response(self, msg: str, extra_info: str):
        self.logger.info(f"Processing agent collection response: {msg}")
        current_state = self.agent_collection.get_current_state()

        if current_state == "chat":
            self._delete_final_bubble()
            if extra_info == "selection":
                self._add_chat_bubble(msg, False)
                self.start_file_process_signal.emit(self.agent_collection)
            else:
                self._add_chat_bubble(msg, is_user=False)

        elif current_state == "file":
            self._add_chat_bubble(msg, False)
            if extra_info == "switch date":
                # 状態を "date" に変更
                self.agent_collection.set_state("date")
                self._add_chat_bubble("自動的に現在日付が設定されました。", False)

        elif current_state == "date":
            self._add_chat_bubble(msg, False)
            if extra_info == "switch task":
                # 状態を "task" に変更して処理を開始
                self.agent_collection.set_state("task")
                self.agent_collection.set_task_speed_mode()
                self._process_waiting_tasks()

        elif current_state == "task":
            self._add_chat_bubble(msg, False)

    def _process_waiting_tasks(self):
        self.logger.info("Process waiting tasks from workflow")
        if self.agent_collection.workflow:
            first_task_name = self.agent_collection.workflow.popleft()
            self.on_task_selected(first_task_name)

    def _process_task_response(self, message: str, dummy: bool):
        self.logger.info(f"Processing task response: {message}")
        self._delete_final_bubble()
        self._add_chat_bubble(message, False)

    def _process_task_operation_signal(
        self, operation_signal: str, task_agent: TaskAgent
    ):
        self.logger.info(f"Task operation signal: {operation_signal}")
        if operation_signal == "file":
            self.send_message_simple_version(self.agent_collection, "yes")
        elif operation_signal == "process" and task_agent.is_fast_mode():
            self.send_message_simple_version(self.agent_collection, "yes")
        elif operation_signal == "next_task":
            current_task_name = task_agent.name
            saved_file_path = task_agent.saved_file_path
            next_task_replaced_file_name = task_agent.next_task_replaced_file_name
            next_task_name = task_agent.next_task_name
            extra_msg = f"前回「{current_task_name}」結果は「{saved_file_path}」に保存されてます。"
            self.on_task_selected(next_task_name, extra_msg)
            self.agent_collection.current_task.replaced_file_name = (
                next_task_replaced_file_name
            )
            self.agent_collection.current_task.replaced_file_path = saved_file_path
        elif operation_signal == "early exit":
            self.agent_collection.set_mgr_mode()
        elif operation_signal == "over":
            if len(self.agent_collection.workflow) > 0:
                self._process_waiting_tasks()
            else:
                self._add_chat_bubble("選んだタスクが終わりました。", False)
                self.agent_collection.set_mgr_mode()
        self.update_file_table()

    def _delete_final_bubble(self):
        if self.chat_display.count() > 0:
            last_index = self.chat_display.count() - 1
            item = self.chat_display.takeItem(last_index)
            del item

    def _add_chat_bubble(self, message, is_user=True, keep_chat=True):
        # メッセージが空の場合はデフォルトの文字列を設定する
        if not message.strip():
            return
        is_html = True if 'class="dataframe">' in message else False
        bubble = ChatBubbleWidget(message, is_user, is_html)
        item = QListWidgetItem()
        item.setSizeHint(bubble.sizeHint())
        self.chat_display.addItem(item)
        self.chat_display.setItemWidget(item, bubble)
        self.chat_display.scrollToBottom()

        if keep_chat:
            role = "user" if is_user else "AI"
            self.current_chat.append((role, message))

    def start_new_chat(self):
        self.logger.info("Starting new chat.")
        self.create_new_chat()
        self.agent_collection.reset_all_task_agents()
        self._initialize_chat()
        self.user_input.setReadOnly(False)

    def create_new_chat(self):
        if self.current_chat:
            self.chat_history.append(self.current_chat)
            self.current_chat = []

        if self.agent_collection.current_task is not None:
            self.agent_collection.current_task.reset()
            self.agent_collection.current_task = None

        self.agent_collection.file_agent.delete_all_files()
        self.agent_collection.workflow.clear()
        self.update_file_table()
        self.chat_display.clear()
        self.update_history_list()

    def update_history_list(self, index=-1):
        self.history_list.clear()
        for i, _ in enumerate(self.chat_history):
            self.history_list.addItem(f"チャット {i + 1}")
        if self.current_chat:
            self.history_list.addItem("現在のチャット")
        if index == -1:
            self.history_list.setCurrentRow(self.history_list.count() - 1)
        else:
            self.history_list.setCurrentRow(index)

    def load_history_chat(self, item):
        index = self.history_list.row(item)
        self.create_new_chat()
        self.user_input.setReadOnly(True)

        if self.current_chat:
            self.chat_history.append(self.current_chat)
        self.current_chat = (
            self.chat_history[index] if index < len(self.chat_history) else []
        )

        self.display_current_chat()
        self.current_chat = []
        self.update_history_list(index=index)

    def display_current_chat(self):
        self.chat_display.clear()
        for role, message in self.current_chat:
            if role == "user":
                self._add_chat_bubble(message, True, False)
            else:
                self._add_chat_bubble(message, False, False)
        final_message = "上記は旧ダイアログの全文である。"
        self._add_chat_bubble(final_message, False, False)

    def _initialize_chat(self):
        welcome_message = """ようこそ！
私は給与計算タスク管理エージェントです！すべてのタスクを紹介し、それぞれのタスクとその処理ルールを詳しく説明することができます。その後、どのタスクに取り組むかを選択するお手伝いをします。"""
        self._add_chat_bubble(welcome_message, False, False)

    def on_task_selected(self, task_name: str, extra_msg: str = None):
        self.logger.info(f"Task selected: {task_name}")
        if self.agent_collection.set_current_task_agent(task_name):
            task = self.agent_collection.get_current_task_agent()
            task.reset()
            self.agent_collection.set_task_mode()
            self.user_input.setReadOnly(False)

            # タスク選択の結果を表示
            message = (
                f"選択されたタスク: {task_name}\nタスクの説明: {task.get_description()}"
            )
            self._add_chat_bubble(message, False)

            # チャット入力時と同様、ファイルアップロードプロセスを開始
            responses, extra_info = self.agent_collection.process_files()
            for resp in responses:
                self._add_chat_bubble(resp, False)

            if extra_msg is not None:
                self._add_chat_bubble(extra_msg, False)

            self.update_history_list()
            self.update_file_table()
        else:
            self._add_chat_bubble("エラー: タスクの選択に失敗しました。", False)

    def closeEvent(self, event):
        self.logger.info("Application closing...")
        if self.mgr_thread.isRunning():
            self.mgr_thread.quit()
            self.mgr_thread.wait()
        super().closeEvent(event)


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    if not os.getenv("LLM_EXCEL_BASE_PATH"):
        os.environ["LLM_EXCEL_BASE_PATH"] = base_path

    os.makedirs(os.path.join(base_path, "json"), exist_ok=True)
    CONFIG_PATH = os.path.join(base_path, "json", "config.json")

    logger.info("Starting AgentCollection initialization")
    agent_collection = AgentCollection(CONFIG_PATH)
    logger.info("AgentCollection initialization complete")

    app = QApplication(sys.argv)
    window = ChatGPTApp(agent_collection)
    window.show()
    sys.exit(app.exec())
