import os
import sys

from langchain_openai import ChatOpenAI
from modules.rag_agent import (
    RAG_Agent,  # RAG_Agent のコードは先ほどのものと同様とします
)
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget

# 環境変数の設定
os.environ["LLM_EXCEL_OPENAI_API_KEY"] = "sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
os.environ["LLM_EXCEL_OPENAI_MODEL"] = "gpt-4o"
# ベースパスはスクリプトのあるディレクトリとする
base_path = os.path.dirname(os.path.abspath(__file__))
os.environ["LLM_EXCEL_BASE_PATH"] = base_path

# ChatOpenAI の初期化（同期的に実行）
print("LLM の初期化開始")
llm = ChatOpenAI(
    model=os.getenv("LLM_EXCEL_OPENAI_MODEL"),
    api_key=os.getenv("LLM_EXCEL_OPENAI_API_KEY"),
    temperature=0,
)
print("LLM の初期化完了")

# RAG_Agent の初期化をイベントループ開始前に実行
print("RAG_Agent の初期化開始（同期実行）")
rag_agent = RAG_Agent(llm)
print("RAG_Agent の初期化完了")


# 以下は単純なウィンドウを作成する例
class MainWindow(QMainWindow):
    def __init__(self, rag_agent):
        super().__init__()
        self.rag_agent = rag_agent
        self.init_ui()

    def init_ui(self):
        label = QLabel("RAG_Agent の初期化が完了しました。")
        layout = QVBoxLayout()
        layout.addWidget(label)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.setWindowTitle("テストウィンドウ")


if __name__ == "__main__":
    print("QApplication の初期化開始")
    app = QApplication(sys.argv)
    window = MainWindow(rag_agent)
    window.show()
    print("ウィンドウ表示完了")
    sys.exit(app.exec())
