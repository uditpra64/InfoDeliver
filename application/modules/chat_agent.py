import logging

from langchain_core.messages import HumanMessage, SystemMessage


class ChatAgent:
    """
    pandas DataFrame の列情報をシステムメッセージとして付与し、
    ユーザーの質問に対して LLM による回答生成を行うエージェント。
    """

    def __init__(self, llm_model):
        self.logger = logging.getLogger(__name__)
        self.llm_model = llm_model
        self.df_column_list = []
        self.additional_vars = {}
        self.system_message = None

    def add_dataframe(self, df, name):
        """DataFrameの列名情報を内部リストに保持してシステムメッセージを更新"""
        column_str = ", ".join(df.columns.to_list())
        self.df_column_list.append((name, column_str))
        self._update_chain()

    def add_variable(self, name, value):
        """追加変数を保持(必要に応じて拡張)"""
        self.additional_vars[name] = value

    def _update_chain(self):
        """df_column_listの内容をシステムメッセージに反映"""
        df_template = """```
        {df_name}.columns
        >>> {df_column}
        ```"""
        df_context = "\n\n".join(
            df_template.format(df_name=df_name, df_column=df_column)
            for df_name, df_column in self.df_column_list
        )

        system = (
            "以下のpandasデータフレームに関する情報があります：\n"
            f"{df_context}\n"
            "上記を参考にユーザーの質問に答えてください。\n"
        )
        self.system_message = SystemMessage(content=system)

    def execute(self, question: str) -> str:
        """チャットを実行し、LLMからの応答を返す"""
        if not self.system_message:
            msg = "システムメッセージ未初期化: データフレームを先に追加してください。"
            self.logger.error(msg)
            raise ValueError(msg)

        self.logger.info("ChatAgent実行")
        messages = [self.system_message, HumanMessage(content=question)]
        try:
            result = self.llm_model.invoke(messages)
            self.logger.debug(f"LLM出力: {result.content}")
            return result.content
        except Exception as e:
            self.logger.exception(f"LLMの呼び出し中にエラー: {str(e)}")
            raise
