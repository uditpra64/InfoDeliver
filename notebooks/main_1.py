import getpass
import os
import sys
# print(sys.prefix)
from langchain_core.prompts import ChatPromptTemplate
from langchain_experimental.tools import PythonAstREPLTool
from langchain.output_parsers.openai_tools import JsonOutputKeyToolsParser
from langchain_openai import ChatOpenAI
import tkinter as tk
from tkinter import filedialog
import pandas as pd
from pandas.core.frame import DataFrame
from pandas.core.series import Series
from io import StringIO
from typing import List
from tabulate import tabulate
import re
import time

class MyBaseError(Exception):
    """Base class for all custom exceptions in this module."""
    def __init__(self, message):
        super().__init__(message)

def print_separation_line(length=80):
    context = "".join("-" for _ in range(length))
    print(context)
    print(context)

def login_openai():
    print("Please input the openai-api key.")
    try:
        os.environ["OPENAI_API_KEY"] = getpass.getpass('Password: ')
    except MyBaseError as e:
        print(f"Caught an error: {e}")
        exit(1)
    print("Successfully connecting to openai!")
    print_separation_line()
    llm = ChatOpenAI(model="gpt-4o-mini")
    return llm

def select_files() -> bool:
    print("Please select one or multiple files!")
    root = tk.Tk()
    root.withdraw()
    file_paths = filedialog.askopenfilenames(title="Select multiple files")
    res = True
    if file_paths:
        results = "\n".join(file for file in file_paths)
        print(f"Select files: \n{results}")
    else:
        print("No files selected!")
        print("The program exits!")
        res = False
    root.destroy()
    print("The root screen is destroyed!")
    if res is False:
        exit(0)
    print_separation_line()
    return file_paths

def is_valid_variable_name(variable_name)->bool:
    pattern = r'^[A-Za-z_][A-Za-z0-9_$]*$'
    return re.match(pattern, variable_name) is not None

def get_file_name_from_user(file_paths)->List:
    num_expected = len(file_paths)
    file_names = []
    print("Please enter a variable name (it must start with a letter or underscore, can only contain letters, numbers, underscores, and the special character '$';\nNo spaces or other special characters are allowed).")
    for idx in range(num_expected):
        cur_file = (file_paths[idx].split('/'))[-1]
        while True:
            name = input(f"Give a name for '{cur_file}' :(1 for default)\n")
            if name == "1":
                print_separation_line()
                return None
            if is_valid_variable_name(name):
                break
            else:
                print(f"Given name {name} does not satisfy the requirement! Input again.")
        file_names.append(name)
    print_separation_line()
    return file_names

def create_multiple_file_chain_info_version_2(csv_file_path_list, LLM_model, names_from_user=None):
    """
    This version supports designates file names from users
    """
    state_user_name = True if names_from_user \
        is not None and len(names_from_user) == len(csv_file_path_list) \
        else False
    df_dict = {}
    df_info_list = []
    buffer = StringIO()
    cur = 1
    print("Load files and give a name for each file as shown:")
    for file_path in csv_file_path_list:

        try:
            df = pd.read_csv(file_path, delimiter=',')
        except MyBaseError as e:
            print(e)
            exit(1)

        file_name = file_path.split('/')[-1]
        print(f"Read the file {file_name}!")
        df.info(buf=buffer)
        df_name = f"df_{cur}" if not state_user_name else names_from_user[cur-1]
        cur += 1
        df_info_list.append((df_name, buffer.getvalue()))
        buffer.flush()
        df_dict[df_name] = df.copy()
        print(f"{df_name} : {file_path}")
    print_separation_line()
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

def prompt_requirement():
    print("Before writing prompt, here are some requirements you should note.")
    print("Ensure your prompt is formal and clear, especially when you specify the file you want to operate on.")
    print("Here are some examples:")
    print("English version: Please rename the column '基本給' as 'basic salary' and return the columns 'スタッフコード' and 'basic salary' from 'df_1'")
    print("Japansese version: 'df_1'の'基本給'を'basic salary'にリネームし、'スタッフコード'と'basic salary'の列を返してください")
    print_separation_line()
    time.sleep(2)

def main():
    print("Hello! This is a program operating csv files with LLM.")
    llm = login_openai()
    file_paths = select_files()
    names_from_user = get_file_name_from_user(file_paths)
    chain = create_multiple_file_chain_info_version_2(file_paths, llm, names_from_user)
    prompt_requirement()
    while True:
        prompt = input("Writing your prompt (1 for exit): ")
        if prompt == "1":
            break
        try:
            answer = chain.invoke(prompt)
        except MyBaseError as e:
            print(e)
            exit(1)
        print("Result:")
        if isinstance(answer, DataFrame) or isinstance(answer, Series):
            print(tabulate(answer))
        else:
            print(answer)
        feedback = input(f"Are you satisfying with the results? (yes or no):")
        if feedback == "no":
            print("Create a new chain due to unsatisfying answers.")
            chain = create_multiple_file_chain_info_version_2(file_paths, llm, names_from_user)
        print_separation_line()
    print("Exit the program.")
    exit(0)

if __name__ == "__main__":
    main()