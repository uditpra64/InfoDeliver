import json
import logging
import os
from datetime import datetime
from typing import List, Optional, Tuple

import pandas as pd
from sqlalchemy import Boolean, Column, DateTime, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.types import TypeDecorator

Base = declarative_base()
logger = logging.getLogger(__name__)


class JSONEncodedDict(TypeDecorator):
    """SQLAlchemyのJSONデータ型を表現"""

    impl = String

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return None


class DataFile(Base):
    """データファイルのメタデータテーブル"""

    __tablename__ = "data_files"

    id = Column(Integer, primary_key=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)
    definition = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    upload_date = Column(DateTime, nullable=False)
    column_info = Column(JSONEncodedDict)
    row_count = Column(Integer)
    task_name = Column(String(255))
    output = Column(Boolean, nullable=False)


class DataTable(Base):
    """CSV/Excelデータの保存テーブル"""

    __tablename__ = "data_values"

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, nullable=False)
    definition = Column(String(255), nullable=False)
    data = Column(JSONEncodedDict, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class FileAgent:
    """
    CSV/Excelファイルの読み込みや保存、DBへの登録などを行う。
    """

    def __init__(self, connection_string=None):
        logger.info("FileAgent を初期化します。")
        if connection_string is None:
            base_path = os.getenv("LLM_EXCEL_BASE_PATH")
            db_path = os.path.join(base_path, "data", "app.db")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            # 毎回削除→作り直し する仕様ならここでremove
            if os.path.isfile(db_path):
                try:
                    os.remove(db_path)
                except PermissionError:
                    logger.warning(f"Could not remove existing database file: {db_path}")
                    logger.warning("Will try to reuse existing database.")
            connection_string = f"sqlite:///{db_path}"

        self.engine = create_engine(connection_string)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.task_configs: dict = None
        logger.info(f"FileAgent 初期化完了: {connection_string}")

    def store_csv_file(
        self,
        df: pd.DataFrame,
        file_name: str,
        file_path: str,
        original_name: str,
        definition: str,
        task_name: str = None,
        output: bool = False,
    ):
        """
        CSV(Excel)をDBに保存
        """
        logger.info(
            f"store_csv_file開始: {file_name}, definition={definition}, task_name={task_name}"
        )
        try:
            file_meta = DataFile(
                file_name=file_name,
                file_path=file_path,
                original_name=original_name,
                definition=definition,
                file_type="csv",
                upload_date=datetime.now(),
                column_info={
                    "columns": df.columns.tolist(),
                    "dtypes": df.dtypes.astype(str).to_dict(),
                },
                row_count=len(df),
                task_name=task_name,
                output=output,
            )
            self.session.add(file_meta)
            self.session.flush()

            chunk_size = 1000
            for i in range(0, len(df), chunk_size):
                chunk = df.iloc[i : i + chunk_size]
                data_records = []
                for _, row in chunk.iterrows():
                    data_records.append(
                        DataTable(
                            file_id=file_meta.id,
                            data=row.to_dict(),
                            definition=definition,
                        )
                    )
                self.session.bulk_save_objects(data_records)

            self.session.commit()
            logger.info(f"ファイルを保存しました。DataFile ID={file_meta.id}")
            return file_meta.id

        except Exception as e:
            self.session.rollback()
            logger.exception("store_csv_file中にエラーが発生")
            raise e

    def load_data_as_df(self, file_id: int) -> pd.DataFrame:
        """file_idを指定してDBからDataFrameを再構築"""
        logger.info(f"load_data_as_df開始: file_id={file_id}")
        try:
            file_meta = self.session.query(DataFile).filter_by(id=file_id).first()
            if not file_meta:
                raise ValueError(f"File ID {file_id} not found")

            data_records = (
                self.session.query(DataTable.data).filter_by(file_id=file_id).all()
            )
            data = [record[0] for record in data_records]
            df = pd.DataFrame(data)

            original_columns = file_meta.column_info["columns"]
            df = df[original_columns]

            return df
        except Exception as e:
            logger.exception("load_data_as_df中にエラーが発生")
            raise e

    def get_file_info(self, file_id: int = None):
        """ファイルのメタデータを取得"""
        logger.debug(f"get_file_info開始: file_id={file_id}")
        query = self.session.query(DataFile)
        if file_id:
            return query.filter_by(id=file_id).first()
        return query.all()

    def get_files_by_task(self, task_name: str) -> List[DataFile]:
        """あるタスクに関連づけられたファイル一覧を取得"""
        logger.debug(f"get_files_by_task開始: task_name={task_name}")
        return self.session.query(DataFile).filter_by(task_name=task_name).all()

    def get_all_files(self) -> List[DataFile]:
        """全ファイルを取得"""
        logger.debug("get_all_files開始")
        return self.session.query(DataFile).all()

    def check_file_uploaded_by_definition(self, definition: str) -> bool:
        """定義名で既にアップロード済みか確認"""
        logger.debug(f"check_file_uploaded_by_definition: definition={definition}")
        file_meta = (
            self.session.query(DataFile).filter_by(definition=definition).first()
        )
        return file_meta is not None

    def load_data_as_df_by_definition(self, definition: str) -> pd.DataFrame:
        """definitionをキーにDBからDataFrameを取得"""
        logger.info(f"load_data_as_df_by_definition開始: definition={definition}")
        try:
            file_meta = (
                self.session.query(DataFile).filter_by(definition=definition).first()
            )
            if not file_meta:
                raise ValueError(f"file definition {definition} not found")

            data_records = (
                self.session.query(DataTable.data)
                .filter_by(definition=definition)
                .all()
            )
            data = [record[0] for record in data_records]
            df = pd.DataFrame(data)

            original_columns = file_meta.column_info["columns"]
            df = df[original_columns]
            return df
        except Exception as e:
            logger.exception("load_data_as_df_by_definition中にエラーが発生")
            raise e

    def delete_file(self, file_id: int):
        """ファイルと関連データを削除"""
        logger.info(f"delete_file開始: file_id={file_id}")
        try:
            self.session.query(DataTable).filter_by(file_id=file_id).delete()
            self.session.query(DataFile).filter_by(id=file_id).delete()
            self.session.commit()
            logger.info(f"delete_file完了: file_id={file_id}")
        except Exception as e:
            self.session.rollback()
            logger.exception("delete_file中にエラーが発生")
            raise e

    def delete_all_files(self):
        """DBを再作成し、全ファイルを削除"""
        logger.warning("DBのテーブルを全削除して再作成します(delete_all_files)")
        try:
            Base.metadata.drop_all(bind=self.engine)
            Base.metadata.create_all(bind=self.engine)
            logger.info("DBをリセットしました。")
        except Exception as e:
            logger.exception("delete_all_files中にエラーが発生")
            raise e

    def check_file_identity(self, file_path: str) -> str:
        """
        アップロードされたファイルに含まれる列などから、
        どのタスクのどのファイル定義に近いかを推定。
        """
        logger.info(f"check_file_identity開始: file_path={file_path}")
        candidates = []
        try:
            for task_dict in self.task_configs.values():
                task_name = task_dict["名称"]
                for file_dict in task_dict["必要なファイル"]:
                    file_name = file_dict["ファイル名前"]
                    file_definition = file_dict["定義"]
                    # 形式が合うか試す
                    res, _ = self._create_df_from_file(file_path, task_name, file_name)
                    if res is not None:
                        candidates.append(
                            {
                                "名称": task_name,
                                "ファイル定義": file_definition,
                            }
                        )
            if len(candidates) == 0:
                return "検索した結果、ファイルの識別ができません。"

            template = "{task_name}-{file_definition}"
            res_info = (
                "アップロードされたファイルは以下のファイルの一つと推定する：\n"
                + "\n".join(
                    template.format(
                        task_name=c["名称"], file_definition=c["ファイル定義"]
                    )
                    for c in candidates
                )
            )
            return res_info

        except Exception as e:
            logger.exception("check_file_identity中にエラーが発生")
            return f"{e}"

    def _create_df_from_file(
        self, file_path: str, folder_name: str, current_file_name: str
    ) -> Tuple[pd.DataFrame, Optional[str]]:
        """
        指定されたfile_pathを読み込み、タスク固有のサンプルファイル(folder_name下)と比較して一致すればdfを返す。
        """
        sample_file_path = self._get_sample_file_path(
            folder_name, current_file_name + "_sample.csv"
        )

        if not os.path.isfile(sample_file_path):
            # サンプルファイル無しの場合は一旦そのまま読み込みだけ試す
            return self._direct_read_file(file_path), None

        # 比較
        sample_df = pd.read_csv(sample_file_path)
        if file_path.lower().endswith(".csv"):
            df = self._direct_read_file(file_path)
            if df is None:
                return None, "CSVファイル読み込み失敗"
            matched, check_info = self._check_dataframe_match(sample_df, df)
            if matched:
                return df, None
            else:
                return None, check_info

        elif file_path.lower().endswith(".xlsx"):
            # EXCELファイル
            excel_file = pd.ExcelFile(file_path)
            num_sheets = len(excel_file.sheet_names)
            check_info_list = []
            for idx in range(num_sheets):
                df = self._read_excel(file_path, sheet_name=idx)
                matched, check_info = self._check_dataframe_match(sample_df, df)
                if matched:
                    return df, None
                else:
                    check_info_list.append(
                        f"シート「{excel_file.sheet_names[idx]}」: \n{check_info}\n"
                    )

            check_info_list.insert(
                0,
                f"サンプルファイル「{current_file_name}_sample.csv」と同じ形式のシートは見つかりませんでした。",
            )
            return None, check_info_list

        return None, None

    def _direct_read_file(self, file_path: str) -> Optional[pd.DataFrame]:
        """CSV/Excelを直接読み込み、DataFrameを返す。"""
        try:
            if file_path.lower().endswith(".csv"):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            return df
        except Exception as e:
            logger.warning(f"ファイル読み込みに失敗: {e}")
            return None

    def _get_sample_file_path(self, folder_name: str, sample_file_name: str) -> str:
        """サンプルファイルのパスを取得"""
        base_path = os.getenv("LLM_EXCEL_BASE_PATH")
        data_folder = os.path.join(base_path, "data", folder_name)
        return os.path.join(data_folder, sample_file_name)

    def _check_dataframe_match(
        self, sample_df: pd.DataFrame, uploaded_df: pd.DataFrame
    ) -> Tuple[bool, str]:
        """
        サンプルとアップロードのカラム構造を比較して一致するか判定。
        一致しない場合、差分を返す。
        """
        if set(sample_df.columns) != set(uploaded_df.columns):
            sample_columns = set(sample_df.columns)
            uploaded_columns = set(uploaded_df.columns)
            only_in_sample = sample_columns - uploaded_columns
            only_in_uploaded = uploaded_columns - sample_columns

            detail_msgs = []
            if only_in_sample:
                detail_msgs.append(
                    "サンプルファイルにのみ存在する列: " + " | ".join(only_in_sample)
                )
            if only_in_uploaded:
                detail_msgs.append(
                    "アップロードファイルにのみ存在する列: "
                    + " | ".join(only_in_uploaded)
                )

            return (
                False,
                "アップロードとサンプルの列名が一致しません:\n"
                + "\n".join(detail_msgs),
            )
        return True, ""

    def _read_excel(self, excel_file_path: str, sheet_name) -> pd.DataFrame:
        """Excelファイルからシートを読み込みDataFrameを返す。"""
        header_idx = self._get_header_index(excel_file_path, sheet_name)
        df = pd.read_excel(excel_file_path, sheet_name=sheet_name, header=header_idx)
        # 'Unnamed:' 'NaN'系の不要列は削除
        df = df.loc[:, ~df.columns.astype(str).str.contains("Unnamed|NaN")]
        # object→stringなどへ変換
        datetime_cols = df.select_dtypes(include=["datetime64[ns]"]).columns
        df[datetime_cols] = df[datetime_cols].astype("string")
        obj_cols = df.select_dtypes(include=["object"]).columns
        df[obj_cols] = df[obj_cols].astype("string")
        return df

    def _get_header_index(self, excel_file_path: str, sheet_name) -> int:
        """スタッフコードor社員番号などが含まれる行をヘッダと推定"""
        df = pd.read_excel(excel_file_path, sheet_name=sheet_name)
        for idx, row in df.iterrows():
            # 行内に社員番号 or スタッフコードがあればそこをヘッダ行とする
            row_str = row.astype(str)
            if any(("社員番号" in val or "スタッフコード" in val) for val in row_str):
                return idx
        return 0
