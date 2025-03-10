from openai import AzureOpenAI


class AzureOpenAIWrapper:
    """
    Azure Open AI のチャット API を呼び出すラッパークラス。
    APIキー、APIバージョン、エンドポイントは以下のコードにハードコードされています。
    この実装は、langchain_openai.ChatOpenAI と同等の使い方ができるように修正されています。
    """

    def __init__(self, model, temperature=0):
        self.model = model
        self.temperature = temperature
        self.__client = AzureOpenAI(
            api_key="c9be74243d9e4db78346018b44592e9a",
            api_version="2024-02-15-preview",
            azure_endpoint="https://formaigpt.openai.azure.com",
        )

    def invoke(self, messages):
        """
        messages は、各要素が {"role": "...", "content": "..."} の dict であると想定します。
        もし messages が文字列ならば、ユーザーメッセージとしてラップします。
        この実装では、送信するコンテンツに image_url は含まず、text タイプのみを送信します。
        """
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        prompt = ""
        for msg in messages:
            if msg.get("role") == "user":
                prompt += msg.get("content") + "\n"
        response = self.__client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}],
                }
            ],
            temperature=self.temperature,
            max_tokens=3000,
        )
        # 辞書アクセスではなく属性アクセスを使用する
        content = response.choices[0].message.content

        class Result:
            pass

        result = Result()
        result.content = content
        return result

    def __call__(self, messages):
        return self.invoke(messages)
