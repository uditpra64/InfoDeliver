import getpass
import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_experimental.tools import PythonAstREPLTool
from langchain.output_parsers.openai_tools import JsonOutputKeyToolsParser
import pandas as pd
from io import StringIO

# os.environ["OPENAI_API_KEY"] = getpass.getpass('Password: ')

from langchain_openai import ChatOpenAI

# llm = ChatOpenAI(model="gpt-4o-mini")
# llmの初期化を変更
llm = ChatOpenAI(model="gpt-4o-mini",
                 openai_api_key="sk-H5M7EgNpycBQX3OTVh_xQBE03TuAnq3Qo8OLlwBJSqT3BlbkFJsfKb-dtrDGI-0CPayuXJFPf5yi1sZsp-Wlx6LCZwMA")


def create_single_file_chain_info_version(csv_file_path, LLM_model):
    df = pd.read_csv(csv_file_path, delimiter=',')
    buffer = StringIO()
    df.info(buf=buffer)
    info_str = buffer.getvalue()
    tool = PythonAstREPLTool(locals={'df': df})
    llm_with_tools = LLM_model.bind_tools([tool], tool_choice=tool.name)
    parser = JsonOutputKeyToolsParser(key_name=tool.name, first_tool_only=True)
    system = f"""You have access to a pandas dataframe `df`. \
    Here is the output of `df.info()`:
    {info_str}
    Given a user question, write the Python code to answer it. ç
    Return ONLY the valid Python code and nothing else. ç
    Don't assume you have access to any libraries other than built-in Python ones, pandas and matplotlib. \
    Always ensure that the code return a pandas Dataframe"""
    prompt = ChatPromptTemplate.from_messages(
        [("system", system), ("human", "{question}")])
    chain = (prompt | llm_with_tools | parser | tool)  # noqa
    return chain


def create_multiple_file_chain_info_version(csv_file_path_list, LLM_model):
    df_dict = {}
    df_info_list = []
    buffer = StringIO()
    cur = 1
    for file_path in csv_file_path_list:
        df = pd.read_csv(file_path, delimiter=',')
        file_name = file_path.split('/')[-1]
        print(f"Read the file {file_name}!")
        df.info(buf=buffer)
        info_lines = buffer.getvalue().splitlines()
        trimmed_info = '\n'.join(info_lines[1:-2])
        df_name = f"csv_{cur}"
        cur += 1
        df_info_list.append((df_name, trimmed_info, file_path))
        buffer.truncate(0)
        buffer.seek(0)
        df_dict[df_name] = df.copy()
        print(f"{df_name} : {file_path}")

    df_template = """```
{df_name}.info()
File Path of {df_name}: {file_path}
>>> {df_info}
```"""

    df_context = "\n\n".join(
        df_template.format(df_name=df_name, df_info=df_info,
                           file_path=file_path)
        for df_name, df_info, file_path in df_info_list
    )

    tool = PythonAstREPLTool(locals=df_dict)
    llm_with_tools = LLM_model.bind_tools([tool], tool_choice=tool.name)
    parser = JsonOutputKeyToolsParser(key_name=tool.name, first_tool_only=True)

    # Modify the system message with clearer instructions if necessary
    system = f"""You have access to several pandas DataFrames. The following information contains the structure (column names and types) for each DataFrame:
    {df_context}


Based on a user's request about the data, generate Python code that uses only built-in Python libraries, pandas(pd), and matplotlib(plt). The code must be valid, complete, and functional.

Here are the key requirements:
1. Include all necessary import statements at the beginning of the code.
2. Ensure the code handles potential column name or index errors by carefully checking the DataFrame's structure.
3. Apply any necessary data preprocessing steps to handle missing data, incorrect data types, or any other common issues that could arise in the data. Pay special attention to ensuring that the data types are correct and consistent across columns to avoid type-related errors.
4. The output of the code must always be a pandas(pd) DataFrame.
5. Return only the Python code—no explanations, comments, or extra text."""

    prompt = ChatPromptTemplate.from_messages(
        [("system", system), ("human", "#依頼\n{question}")])

    chain = (prompt | llm_with_tools | parser | tool)  # noqa
    return chain


'''
def csvtool() :

    file_path_1 = '0924_テスト用データ(9月分)/INPUTデータ(9月)/納品物作成/2_yonosuke/①今月給与明細データ.csv'
    file_path_2 = '0924_テスト用データ(9月分)/INPUTデータ(9月)/納品物作成/2_yonosuke/③9月賞与データ.csv'

    multiple_file_chain = create_multiple_file_chain_info_version([file_path_1, file_path_2], llm)

    prompt = " 通勤手当が10000以上の授業員を出力してください"
    ques = {"question": prompt}
    multiple_file_chain.invoke(prompt)
'''


def csvtool(file_path_1, file_path_2, prompt):
    multiple_file_chain = create_multiple_file_chain_info_version(
        [file_path_1, file_path_2], llm)
    ques = {"question": prompt}
    return multiple_file_chain.invoke(ques)


def main():
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description='CSVツール - CSVファイルの分析と処理を行います。')
    parser.add_argument('-csv', action='append',
                        help='CSVファイルのパス（1つまたは2つ指定可能）')
    parser.add_argument('-prompt', help='分析や処理のためのプロンプト')

    args = parser.parse_args()

    if not args.csv or len(args.csv) > 2:
        print("エラー: CSVファイルは1つまたは2つ指定してください。")
        parser.print_help()
        sys.exit(1)

    if not args.prompt:
        print("エラー: プロンプトを指定してください。")
        parser.print_help()
        sys.exit(1)

    if len(args.csv) == 1:
        chain = create_single_file_chain_info_version(args.csv[0], llm)
    else:
        chain = create_multiple_file_chain_info_version(args.csv, llm)

    result = chain.invoke({"question": args.prompt})
    print(result)

    # 結果がDataFrameであることを確認し、CSVファイルとして保存
    if isinstance(result, pd.DataFrame):
        output_path = 'output.csv'
        result.to_csv(output_path, index=False)
        print(f"結果を {output_path} に保存しました。")
    else:
        print("結果はDataFrameではないため、CSVファイルとして保存できません。")


if __name__ == "__main__":
    main()
