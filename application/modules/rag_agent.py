import faulthandler
import logging
import os
from typing import List

from langchain import hub

# Embedding を Hugging Face のモデルに変更
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

faulthandler.enable()
logger = logging.getLogger(__name__)


def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)


class RAG_Agent:
    def __init__(self, llm):
        logger.info("RAG_Agentを初期化します。")
        try:
            embedding = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            logger.debug("HuggingFaceEmbeddings インスタンス生成OK")
            test_vector = embedding.embed_query("Hello")
            logger.debug(f"embed_query実行OK. 長さ={len(test_vector)}")
        except Exception:
            logger.exception("Embedding生成時に例外が発生しました。")
            raise

        self.embedding = embedding
        self.llm = llm
        self.rag_chain = self._create_rag_chain()
        logger.info("RAG_Agent初期化完了")

    def _get_all_file_paths(self) -> List[str]:
        base_path = os.getenv("LLM_EXCEL_BASE_PATH")
        rule_folder = os.path.join(base_path, "rule")
        file_paths = []
        for root, _, files in os.walk(rule_folder):
            for file in files:
                suffix = os.path.splitext(file)[1]
                if suffix != ".md":
                    continue
                if "説明用" in file or "sample" in file:
                    continue
                file_paths.append(os.path.join(root, file))
        return file_paths

    def _create_retriever_for_multiple_files(self):
        logger.info("RAG用に複数ファイルからRetrieverを作成します。")
        file_paths = self._get_all_file_paths()
        base_path = os.getenv("LLM_EXCEL_BASE_PATH")
        rule_folder = os.path.join(base_path,"rule")
        if len(file_paths) == 0:
            msg = f"No rules found in {rule_folder}, using application rules"
            logger.warning(msg)
    
            # Try to use rules from application directory as fallback
            app_rule_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rule")
            for root, _, files in os.walk(app_rule_folder):
                for file in files:
                    suffix = os.path.splitext(file)[1]
                    if suffix != ".md":
                        continue
                    if "説明用" in file or "sample" in file:
                        continue
                    file_paths.append(os.path.join(root, file))
            
            # If still no files, create a default
            if len(file_paths) == 0:
                default_rule_path = os.path.join(rule_folder, "payroll_rule.md")
                with open(default_rule_path, "w", encoding="utf-8") as f:
                    f.write("# Payroll Rule\n\nStandard calculation rules apply.\n")
                file_paths = [default_rule_path]

        splits = []
        for file_path in file_paths:
            loader = TextLoader(file_path, encoding="utf-8-sig")
            docs = loader.load()
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000, chunk_overlap=200
            )
            splitted_docs = text_splitter.split_documents(docs)
            splits.extend(splitted_docs)
            logger.debug(f"ファイル {file_path} は {len(splitted_docs)} 個に分割")

        logger.debug(f"合計 {len(splits)} 個の分割ドキュメントを作成します。")
        vectorstore = FAISS.from_documents(documents=splits, embedding=self.embedding)
        logger.debug("Vectorstore(Faiss)作成完了")
        retriever = vectorstore.as_retriever(k=4)
        return retriever

    def _create_rag_chain(self):
        logger.debug("RAG用chainを作成します。")
        retriever = self._create_retriever_for_multiple_files()
        prompt = hub.pull("rlm/rag-prompt")
        rag_chain = (
            {"context": retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | self.llm
            | StrOutputParser()
        )
        return rag_chain

    def execute(self, question: str) -> str:
        logger.info(f"RAG_Agentに問い合わせ実行: {question}")
        suffix = "(タスクを紹介する場合必ず定義を含め)"
        result = self.rag_chain.invoke(question + suffix)
        logger.debug(f"RAG応答: {result}")
        return result
