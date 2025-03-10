import logging
import os
from collections import deque
from difflib import SequenceMatcher
from typing import List, Tuple

from langchain.chains.question_answering import load_qa_chain
from langchain_community.document_loaders import TextLoader
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

logger = logging.getLogger(__name__)


def similarity_ratio(word1, word2):
    return SequenceMatcher(None, word1, word2).ratio()


def return_most_similiar_word(input_word: str, word_list: list):
    idx = 0
    max_score = 0
    for i, word in enumerate(word_list):
        score = similarity_ratio(input_word, word)
        if score > max_score:
            max_score = score
            idx = i
    return word_list[idx]


class State(TypedDict):
    messages: list
    task_info_dict: dict
    judge_strings: list
    memory: List[Tuple[str, str]]


mgr_system_prompt = """You are a manager of an application with many tasks. 
You are allowed to do one of those jobs based on user's query:
1. introduce the overall general about tasks that this application can support, and make a summary. Query what task you should introduce.
2. introduce the selected task by user in detail, including its processing rule. Query what task user wants to choose.
3. give some advice to help user to choose one task based on his/her needs. Query whether this task satisfies the user' needs.
4. If user wants to select a task, multiple tasks or even all the tasks, return task names in order separated by '|'. Make sure not to misunderstand.
5. If user wants to generate rule for processing, generate and return the rule.
All the responeses except task name string must be in Japanese.\n
"""


class MgrBot:
    def __init__(self, llm):
        self.llm = llm

    def __call__(self, state: State):
        logger.debug("MgrBot呼び出し")
        message = state["messages"][-1] if len(state.get("messages", [])) > 0 else None
        if not message:
            return state

        system = mgr_system_prompt
        try:
            judge_str = state["judge_strings"][-1]
            if judge_str in [
                "general introduction",
                "advice",
                "selection",
                "others",
                "comparison",
            ]:
                task_template = (
                    """`名称`: `{task_name}`, `概要`: `{task_explaination}`"""
                )
                all_task_info = "\n".join(
                    task_template.format(
                        task_name=task["名称"],
                        task_explaination=task["概要"],
                    )
                    for task in state["task_info_dict"].values()
                )
                system += "\nAll the available tasks are as below\n"
                system += all_task_info
            elif judge_str == "generation":
                rule_generate_prompt = """
If you need to generate processing rules, please follow the format of appended document and remove all the comments in the generated rule\n"""
                base_path = os.getenv("LLM_EXCEL_BASE_PATH")
                rule_path = os.path.join(base_path, "rule", "納品物作成_sample.md")
                loader = TextLoader(rule_path, autodetect_encoding=True)
                documents = loader.load()
                qa_chain = load_qa_chain(self.llm, chain_type="stuff")

                if state["memory"]:
                    memory_template = ChatPromptTemplate.from_messages(
                        [("placeholder", "{conversation}")]
                    )
                    memory = memory_template.invoke(
                        {"conversation": [(role, msg) for role, msg in state["memory"]]}
                    )
                else:
                    memory = ""

                answer = qa_chain.invoke(
                    {
                        "system": system + rule_generate_prompt,
                        "question": message.content,
                        "input_documents": documents,
                        "context": memory.to_string() if memory else "",
                    }
                )
                state["messages"].append(AIMessage(answer["output_text"]))
                return state
            else:
                # タスクごとの詳細表示（judge_strが実際にタスク名の場合）
                task = state["task_info_dict"].get(judge_str, None)
                if task is not None:
                    file_template = """
                    'ファイル名前': {file_name}
                    'ファイル説明': {file_explanation}
                    '必要': {needed}\n
                    """
                    system += f"\nFor `名称`: {task['名称']}, `概要`: {task['概要']}. All the required files are as below\n"
                    all_file_info = "".join(
                        file_template.format(
                            file_name=f["ファイル名前"],
                            file_explanation=f["ファイル説明"],
                            needed=f["必要"],
                        )
                        for f in task["必要なファイル"]
                    )
                    system += all_file_info

                    rule_file_name = task["ルール"]
                    base_path = os.getenv("LLM_EXCEL_BASE_PATH")
                    rule_path = os.path.join(base_path, "rule", rule_file_name)
                    with open(rule_path, "r", encoding="utf-8") as f:
                        prompt_content = f.read()
                    system += f"\nProcessing rule:\n{prompt_content}"
            message_list = [("system", system)]
            if state["memory"]:
                message_list.extend(state["memory"])
            message_list.append(("human", "{question}"))
            prompt = ChatPromptTemplate.from_messages(message_list)
            res_msg = (prompt | self.llm).invoke(message.content)
            state["messages"].append(res_msg)
        except Exception as e:
            logger.exception("MgrBot処理中にエラーが発生")
            state["messages"].append(AIMessage(str(e)))
        return state


judge_prompt = """You are required to assess the type of requirement from human based on the Final Keynote what the human said.
1. If about general introduction, return a string "general introduction"
2. If related to comparison, return a string "comparison".
3. If related to one specific task introduction, just return `タスク名前` of the task.
4. If about asking advice on how to select tasks, return a string "advice"
5. If about deciding to select a task, multiple tasks or even all the tasks, return a string "selection"
6. If about generating something, return a string "generation"
7. If none of the above, return a string "others".\n
"""


class JudgeBot:
    def __init__(self, llm):
        self.llm = llm
        self.operation_list = [
            "general introduction",
            "advice",
            "selection",
            "generation",
            "comparison",
            "others",
        ]

    def __call__(self, state: State):
        logger.debug("JudgeBot呼び出し")
        message = state["messages"][-1] if len(state.get("messages", [])) > 0 else None
        if not message:
            return state

        system = judge_prompt
        task_template = """`名称`: {task_name},  `概要`: {task_explaination}\n"""
        all_task_info = "".join(
            task_template.format(
                task_name=task["名称"],
                task_explaination=task["概要"],
            )
            for task in state["task_info_dict"].values()
        )
        system += "\nAll the available tasks are as below\n"
        system += all_task_info
        message_list = []
        if state["memory"]:
            message_list.extend(state["memory"])

        message_list.append(("system", system))
        message_list.append(("human", "{question}"))
        prompt = ChatPromptTemplate.from_messages(message_list)
        response = (prompt | self.llm).invoke(message.content)
        res = response.content

        task_name_list = [task["名称"] for task in state["task_info_dict"].values()]
        task_name_list.extend(self.operation_list)

        result = return_most_similiar_word(res, task_name_list)
        state["judge_strings"].append(result)
        return state


class WorkflowAgent:
    def __init__(self, llm, task_info_dict: dict, max_memory_len=4):
        logger.info("WorkflowAgent(deprecated) 初期化開始")
        self.llm = llm
        self.task_info_dict = task_info_dict
        self.graph = self._create_graph()
        self.past_messages: List[tuple] = []
        self.max_memory_len = max_memory_len

        self.workflow: deque[str] = deque()
        logger.info("WorkflowAgent(deprecated) 初期化完了")

    def __iter__(self):
        return iter(self.workflow)

    def __len__(self) -> int:
        return len(self.workflow)

    def pop(self) -> str:
        return self.workflow.popleft()

    def push(self, task_name: str):
        self.workflow.append(task_name)

    def clear(self):
        self.workflow.clear()

    def clear_memory(self):
        self.past_messages.clear()

    def _create_graph(self) -> StateGraph:
        logger.debug("workflow用StateGraph生成")
        graph_builder = StateGraph(State)
        self.mgrbot = MgrBot(llm=self.llm)
        self.judgebot = JudgeBot(llm=self.llm)
        graph_builder.add_node("mgr", self.mgrbot)
        graph_builder.add_node("judge", self.judgebot)
        graph_builder.add_edge(START, "judge")
        graph_builder.add_edge("judge", "mgr")
        graph_builder.add_edge("mgr", END)
        graph = graph_builder.compile()
        return graph

    def add_memory(self, msg, is_human=False):
        logger.debug("WorkflowAgent(deprecated) add_memory呼び出し")
        if is_human:
            self.past_messages.append(("human", msg))
        else:
            self.past_messages.append(("ai", msg))
        while len(self.past_messages) >= self.max_memory_len:
            self.past_messages.pop(0)

    def execute(self, prompt: str) -> Tuple[str, str]:
        logger.info(f"WorkflowAgent(deprecated) execute呼び出し prompt: {prompt}")
        memory = self.past_messages if self.past_messages else None

        message_list = [HumanMessage(prompt)]
        judge_strings = []
        state = State(
            messages=message_list,
            task_info_dict=self.task_info_dict,
            judge_strings=judge_strings,
            memory=memory,
        )
        res = self.graph.stream(state)
        for event in res:
            for v in event.values():
                state = v

        self.past_messages.append(("human", prompt))
        self.past_messages.append(("ai", state["messages"][-1].content))
        while len(self.past_messages) >= self.max_memory_len:
            self.past_messages.pop(0)

        judge = state["judge_strings"][-1]
        msg = state["messages"][-1].content

        if judge != "selection":
            return msg, judge

        task_name_list = msg.split("|")
        waiting_task = []
        for task_name in task_name_list:
            choosen_task_name = return_most_similiar_word(
                task_name, list(self.task_info_dict.keys())
            )
            if choosen_task_name is not None:
                waiting_task.append(choosen_task_name)

        waiting_task = sorted(waiting_task)
        for tname in waiting_task:
            self.push(tname)
        info = "選んだタスクが以下の順番に処理する:\n" + "->".join(
            tname for tname in waiting_task
        )

        return info, judge
