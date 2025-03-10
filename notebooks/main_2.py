import getpass
import os
import sys
from openai import OpenAI
import pandas as pd
from io import StringIO
from PyQt6.QtGui import QKeySequence
from langchain_core.prompts import ChatPromptTemplate
from langchain_experimental.tools import PythonAstREPLTool
from langchain.output_parsers.openai_tools import JsonOutputKeyToolsParser
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTextEdit,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QFileDialog,
    QLabel,
    QListWidget,
    QSplitter,
    QScrollArea,
    QSizePolicy,

)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, pyqtSlot
from pandas.core.frame import DataFrame
from pandas.core.series import Series
import tabulate
import threading

# 環境変数からAPIキーを取得
api_key = "sk-pzmVDXe1-rxgtV34fEob57Owp9b7Z7_k-jYKmFaguDT3BlbkFJXR835WsPGSV7P_sjJXS2QGOJBIxgW5wSzwqExklvAA"
# client = OpenAI(api_key=api_key)

# LLMモデルのインスタンスを作成
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini", api_key=api_key)

class ChatObject(QObject):
    #This object is resposible for chatting with LLM
    message = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()

    def run(self, LLM_chain, query, mutex):
        mutex.acquire()
        ai_response = LLM_chain.invoke(query)
        # if isinstance(ai_response, DataFrame) or isinstance(ai_response, Series):
        #     ai_response = tabulate.tabulate(ai_response)  
        ai_response = f"{ai_response}"
        self.message.emit(ai_response)
        mutex.release()
    
# ChatGPTAppクラス, QMainWindowを継承
class ChatGPTApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChatGPT Desktop App")
        self.setGeometry(100, 100, 1000, 800)

        self.chat_history = []
        self.current_chat = []

        # メインウィジェットとレイアウトの設定
        main_widget = QWidget()
        main_layout = QHBoxLayout()

        # 左側のチャット履歴リスト
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.load_chat)
        main_layout.addWidget(self.history_list, 1)

        # 右側のチャット表示と入力エリア
        right_widget = QWidget()
        right_layout = QVBoxLayout()

        # scroll bar area
        self.sidebar_widget = QWidget()
        self.sidebar_layout = QHBoxLayout(self.sidebar_widget)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)  # Make the scroll area resize with the sidebar
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)  # Always show the scrollbar
        self.scroll_area.setWidget(self.sidebar_widget)
        right_layout.addWidget(self.scroll_area)

        self.add_button_to_sidebar("会話")
        self.add_button_to_sidebar("業務")
        self.add_button_to_sidebar("納品物")
        self.add_button_to_sidebar("未定1")
        self.add_button_to_sidebar("未定2")
        self.add_button_to_sidebar("未定3")
        self.add_button_to_sidebar("未定4")
        self.add_button_to_sidebar("未定5")

        # チャット表示用のテキストエディット
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        right_layout.addWidget(self.chat_display, 7)

        # ファイルアップロード, recreate chain レイアウト
        layerout_1 = QHBoxLayout()
        self.file_path_list = None
        self.file_upload_button = QPushButton("いくつかのcsvファイルを選択してください")
        self.file_upload_button.clicked.connect(self.select_mutiple_files)
        layerout_1.addWidget(self.file_upload_button)

        self.update_chain_button = QPushButton("チェーンを更新する")
        self.update_chain_button.clicked.connect(self.update_chain)
        layerout_1.addWidget(self.update_chain_button)

        right_layout.addLayout(layerout_1)

        # ユーザー入力用のラインエディット
        self.user_input = QTextEdit()
        self.user_input.setPlaceholderText("メッセージを入力してください...")
        self.user_input.setMinimumHeight(10)  # 最小の高さを設定
        self.user_input.setMaximumHeight(150)  # 最小の高さを設定
        right_layout.addWidget(self.user_input)

        # 送信ボタン
        self.send_button = QPushButton("送信")
        self.send_button_object = ChatObject()
        self.send_button_thread = QThread()
        self.send_button_object.moveToThread(self.send_button_thread)
        self.send_button.clicked.connect(self.send_message)
        self.send_button_object.message.connect(self.get_response)
        right_layout.addWidget(self.send_button)

        # set the layerout for the right side area
        right_widget.setLayout(right_layout)
        main_layout.addWidget(right_widget, 3)

        # スプリッターの追加
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.history_list)
        splitter.addWidget(right_widget)
        main_layout.addWidget(splitter)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # エンターキーを送信ボタンに接続
        # self.user_input.returnPressed.connect(self.send_button.click)

        # 新しいチャットボタンの追加
        self.new_chat_button = QPushButton("新しいチャット")
        self.new_chat_button.clicked.connect(self.start_new_chat)
        right_layout.addWidget(self.new_chat_button)

        self._init_chat()
        self.llm_chain = None
        self.chain_mutex = threading.Lock()

    def showEvent(self, event):
        self.send_button_thread.start()

    def closeEvent(self, event):
        self.send_button_thread.quit()
        self.send_button_thread.wait()
        event.accept()

    def add_button_to_sidebar(self, button_text):
        """Add a button to the sidebar."""
        button = QPushButton(button_text)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Allow button to expand
        self.sidebar_layout.addWidget(button)


    def select_mutiple_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "いくつかのcsvファイルを選択してください", "", "All Files (*);;Text Files (*.csv)")
        if files:
            self.file_path_list = files
            self.llm_chain = self._create_multiple_file_chain_info_version_2(files, llm)
            self.file_upload_button.setText("すべてのファイルをアップデートした")
        else:
            # display info on failing selecting files
            self.chat_display.append("ファイル選択失敗\n")

    def update_chain(self):
        self.chain_mutex.acquire()
        self.llm_chain = self._create_multiple_file_chain_info_version_2(self.file_path_list, llm)
        self.chain_mutex.release()
    
    @pyqtSlot(str)
    def get_response(self, ai_response):      
        self.chat_display.append(f"AI: {ai_response}")  # AIの応答を表示
        self.chat_display.append(
            f"----------------------------------------------------------------------------"
        )
        self.current_chat.append({"role": "assistant", "content": ai_response})
        return

    def send_message(self):
        user_message = self.user_input.toPlainText()
        if user_message is None:
            self.chat_display.append("プロンプトを入力してください\n")
            return
        if self.llm_chain is None or self.file_path_list is None:
            self.chat_display.append("最初にファイルをアップロードしてください\n")
            return
        
        self.chat_display.append(f"ユーザー: {user_message}")
        self.current_chat.append({"role": "user", "content": user_message})

        # create_multiple_file_chain_info_versionを呼び出す
        # チェーンを実行するためのメッセージを準備
        question = user_message  # ユーザーからの質問を利用
        self.send_button_object.run(self.llm_chain, question, self.chain_mutex)
        self.user_input.clear()
        # ai_response = self.llm_chain.invoke(question)  # チェーンを呼び出し

    def handle_ai_response(self, response):
        self.chat_display.append(f"AI: {response}")
        self.current_chat.append({"role": "assistant", "content": response})
        self.update_history_list()

    def start_new_chat(self):
        if self.current_chat:
            self.chat_history.append(self.current_chat)
        self.current_chat = []
        self.chat_display.clear()
        self.update_history_list()

    def update_history_list(self):
        self.history_list.clear()
        for i, chat in enumerate(self.chat_history):
            self.history_list.addItem(f"チャット {i+1}")
        if self.current_chat:
            self.history_list.addItem("現在のチャット")
        self.history_list.setCurrentRow(self.history_list.count() - 1)

    def load_chat(self, item):
        index = self.history_list.row(item)
        if index < len(self.chat_history):
            self.current_chat = self.chat_history[index]
        else:
            self.current_chat = []
        self.display_current_chat()

    def display_current_chat(self):
        self.chat_display.clear()
        for message in self.current_chat:
            role = "ユーザー" if message["role"] == "user" else "AI"
            self.chat_display.append(f"{role}: {message['content']}")

    def _init_chat(self):
        self.chat_display.append("ようこそ まずはファイルのアップロードとプロンプトの送信から始めましょう!\n")
        
    #--------------------------------function utilites------------------------------
    def _create_multiple_file_chain_info_version_2(self, csv_file_path_list, LLM_model, names_from_user=None):
        """
        This version supports designates file names from users
        """
        state_user_name = True if names_from_user \
            is not None and len(names_from_user) == len(csv_file_path_list) \
            else False
        df_dict = {}
        df_info_list = []
        buffer = StringIO()
        self.chat_display.append("ファイルを指定する名前：元のファイル名\n")
        cur = 1
        for file_path in csv_file_path_list:
            try:
                df = pd.read_csv(file_path, delimiter=',')
            except Exception as e:
                info = f"{file_path} 条件を満たしていない\nもう一度ファイルをアップロードしてください\n"
                self.file_path_list = None
                self.chat_display(info)
                return None
            
            file_name = file_path.split('/')[-1]
            df.info(buf=buffer)
            df_name = f"file{cur}" if not state_user_name else names_from_user[cur-1]
            cur += 1
            df_info_list.append((df_name, buffer.getvalue()))
            buffer.flush()
            df_dict[df_name] = df.copy()
            info = f"{df_name} : {file_name}\n"
            self.chat_display.append(info)

        self.chat_display.append("これがすべてのファイルです。それが正しいかどうか確認してください\n")
        df_template = """```python
        {df_name}.info()
        >>> {df_info}
        ```"""
        df_context = "\n\n".join(
            df_template.format(df_name=df_name, df_info=df_info)
            for df_name, df_info in df_info_list
        )
        tool = PythonAstREPLTool(locals=df_dict)
        llm_with_tools = LLM_model.bind_tools([tool], tool_choice=tool.name)
        parser = JsonOutputKeyToolsParser(key_name=tool.name, first_tool_only=True)
        system = f"""You have access to a number of pandas dataframes. \
        Here is the info from each dataframe`:
        {df_context}
        Given a user question about the dataframes, write the Python code to answer it. \
        Return ONLY the valid Python code and nothing else. \
        Don't assume you have access to any libraries other than built-in Python ones, pandas and matplotlib. \
        Ensure that there is not index error when referring to a column name. \
        Always ENSURE that the code return a pandas Dataframe.
        Please CHECKT column name for each dataframe carefully.
        """
        prompt = ChatPromptTemplate.from_messages([("system", system), ("human", "{question}")])
        chain = (prompt | llm_with_tools | parser | tool)  # noqa
        return chain


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChatGPTApp()
    window.show()
    sys.exit(app.exec())
