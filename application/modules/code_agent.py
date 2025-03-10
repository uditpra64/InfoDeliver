# code_agent.py

import logging
from datetime import date
from io import StringIO

from langchain.output_parsers.openai_tools import JsonOutputKeyToolsParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_experimental.tools import PythonAstREPLTool


class CodeAgent:
    """
    pandas DataFrameを扱うPythonコードをLLMに生成させるエージェント。
    """

    def __init__(self, llm_model):
        self.logger = logging.getLogger(__name__)
        self.llm_model = llm_model
        self.df_dict = {}
        self.df_info_list = []
        self.additional_vars = {}
        self.chain = None

    def add_dataframe(self, df, name):
        """DataFrameを内部に登録し、infoを記録してチェーンを更新"""
        self.df_dict[name] = df
        buffer = StringIO()
        df.info(buf=buffer)
        self.df_info_list.append((name, buffer.getvalue()))
        self._update_chain()

    def add_variable(self, value, name):
        """追加変数を登録（必要に応じて拡張可）"""
        self.additional_vars[name] = value
        self._update_chain()

    def _update_chain(self, current_date=None, function_name=None):
        """チェーン（LLM+ツール+パーサー）を再構築"""
        if current_date is None:
            current_date = date.today()
        if not function_name:
            function_name = "my_function"

        df_template = """```python
        {df_name}.info()
        >>> {df_info}
        ```"""
        df_context = "\n\n".join(
            df_template.format(df_name=df_name, df_info=df_info)
            for df_name, df_info in self.df_info_list
        )
        # { と } をエスケープしておく
        df_context = df_context.replace("{", "{{").replace("}", "}}")

        tool = PythonAstREPLTool(locals=self.df_dict)
        llm_with_tools = self.llm_model.bind_tools([tool], tool_choice=tool.name)
        parser = JsonOutputKeyToolsParser(key_name=tool.name, first_tool_only=True)

        # systemメッセージで「pandasを必ずimportする」ように強調
        system = f"""以下のpandasデータフレーム情報があります：
        {df_context}

        Based on a user's request about the data, generate Python code that uses only built-in Python libraries, pandas.
        1. 必要なimport文をコード冒頭に含める（必ず "import pandas as pd" を記述すること）
        2. データ型や欠損値の処理を正しく行う
        3. 中間結果はDataFrameを活用し保持
        4. 出力は一切の説明文無しで純粋なPythonコードのみ
        5. 作成する関数名は '{function_name}'（引数は '社員番号'(str)と 'df_dict'(dict)）
        6. 現在日付は {current_date} (YYYY-MM-DD)
        """

        try:
            self.chain = {
                "prompt": ChatPromptTemplate.from_messages(
                    [("system", system), ("human", "{question}")]
                ),
                "llm_with_tools": llm_with_tools,
                "parser": parser,
                "tool": tool,
            }
            self.logger.debug("コード生成用チェーンを構築完了")
        except Exception as e:
            self.logger.exception(f"チェーン構築中にエラー: {str(e)}")
            raise

    def execute(self, question) -> str:
        """ユーザーの質問を元にPythonコードを生成して返す"""
        if not self.chain:
            msg = "チェーン未初期化: DataFrameを追加してください。"
            self.logger.error(msg)
            raise ValueError(msg)

        self.logger.info(f"CodeAgent実行: question={question}")
        try:
            # 1) プロンプトを生成
            prompt_output = self.chain["prompt"].invoke(question)
            self.logger.debug(f"プロンプト出力: {prompt_output}")

            # 2) LLMを実行
            llm_output = self.chain["llm_with_tools"].invoke(prompt_output)
            self.logger.debug(f"LLM出力: {llm_output}")

            # 3) パーサーを適用し、Pythonコードを取り出す
            parser_output = self.chain["parser"].invoke(llm_output)
            self.logger.debug(f"パーサー出力: {parser_output}")

            code_str = parser_output["query"]

            # 4) **ここが重要: "import pandas as pd" を後処理で強制追加**
            if "import pandas as pd" not in code_str:
                # まだ書かれていないなら先頭に挿入
                code_str = "import pandas as pd\n" + code_str

            # 必要に応じて "import numpy as np" なども強制したいなら同様の処理を追加

            return code_str

        except Exception as e:
            self.logger.exception(f"チェーン実行中にエラー: {str(e)}")
            raise
