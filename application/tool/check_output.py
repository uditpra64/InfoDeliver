import logging
import os
from datetime import datetime
from typing import Dict, List, Tuple

import pandas as pd
from dotenv import load_dotenv


class CustomFormatter(logging.Formatter):
    """カスタムログフォーマッタ"""

    def __init__(self):
        super().__init__()
        self.header_format = "%(message)s"
        self.info_format = "  %(message)s"
        self.warning_format = "  ⚠ %(message)s"
        self.error_format = "  ❌ %(message)s"
        self.success_format = "  ✓ %(message)s"

    def format(self, record):
        # オリジナルのフォーマットを保存
        original_format = self._style._fmt

        # ログレベルに応じてフォーマットを変更
        if record.levelno == logging.INFO:
            self._style._fmt = self.info_format
        elif record.levelno == logging.WARNING:
            self._style._fmt = self.warning_format
        elif record.levelno == logging.ERROR:
            self._style._fmt = self.error_format
        elif record.levelno == logging.CRITICAL:
            self._style._fmt = self.header_format

        # メッセージをフォーマット
        result = logging.Formatter.format(self, record)

        # オリジナルのフォーマットを復元
        self._style._fmt = original_format

        return result


def setup_logger():
    """ロガーのセットアップ"""
    # ロガーの作成
    logger = logging.getLogger("CSVComparator")
    logger.setLevel(logging.INFO)

    # ファイルハンドラの設定
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_handler = logging.FileHandler(
        f"csv_comparison_{timestamp}.log", encoding="utf-8"
    )
    file_handler.setFormatter(CustomFormatter())

    # コンソールハンドラの設定
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(CustomFormatter())

    # ハンドラの追加
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


class CSVComparator:
    def __init__(self):
        self.logger = setup_logger()

        # .envファイルの読み込み
        load_dotenv()

        # 環境変数から各CSVのパスを取得
        self.correct_csv_path = os.getenv("CORRECT_CSV_PATH")
        self.output_csv_path = os.getenv("OUTPUT_CSV_PATH")

        if not self.correct_csv_path or not self.output_csv_path:
            raise ValueError("CSVファイルのパスが.envファイルで指定されていません")

    def load_csv_files(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """CSVファイルを読み込む"""
        try:
            self.logger.critical("\n=== CSVファイル読み込み ===")
            correct_df = pd.read_csv(self.correct_csv_path)
            self.logger.info(f"正解CSVを読み込みました: {self.correct_csv_path}")
            self.logger.info(f"  - 行数: {len(correct_df)}")
            self.logger.info(f"  - カラム数: {len(correct_df.columns)}")

            output_df = pd.read_csv(self.output_csv_path)
            self.logger.info(f"出力CSVを読み込みました: {self.output_csv_path}")
            self.logger.info(f"  - 行数: {len(output_df)}")
            self.logger.info(f"  - カラム数: {len(output_df.columns)}")

            return correct_df, output_df
        except Exception as e:
            self.logger.error(f"CSVファイルの読み込みに失敗しました: {str(e)}")
            raise

    def compare_structure(
        self, correct_df: pd.DataFrame, output_df: pd.DataFrame
    ) -> Dict:
        """CSVの構造を比較する"""
        self.logger.critical("\n=== 構造の比較 ===")
        structure_comparison = {
            "columns_match": True,
            "row_count_match": True,
            "differences": [],
        }

        # カラム名の比較
        correct_columns = list(correct_df.columns)
        output_columns = list(output_df.columns)

        if correct_columns == output_columns:
            self.logger.info("✓ カラム構造: 一致")
        else:
            structure_comparison["columns_match"] = False
            self.logger.warning("カラム構造: 不一致")
            self.logger.info("正解CSVのカラム:")
            for col in correct_columns:
                self.logger.info(f"  - {col}")
            self.logger.info("出力CSVのカラム:")
            for col in output_columns:
                self.logger.info(f"  - {col}")

            # 違いの詳細を記録
            only_in_correct = set(correct_columns) - set(output_columns)
            only_in_output = set(output_columns) - set(correct_columns)

            if only_in_correct:
                self.logger.warning("正解CSVにのみ存在するカラム:")
                for col in only_in_correct:
                    self.logger.info(f"  - {col}")

            if only_in_output:
                self.logger.warning("出力CSVにのみ存在するカラム:")
                for col in only_in_output:
                    self.logger.info(f"  - {col}")

        # 行数の比較
        if len(correct_df) == len(output_df):
            self.logger.info("✓ 行数: 一致")
        else:
            structure_comparison["row_count_match"] = False
            self.logger.warning("行数: 不一致")
            self.logger.info(f"  - 正解CSV: {len(correct_df)}行")
            self.logger.info(f"  - 出力CSV: {len(output_df)}行")

        return structure_comparison

    def compare_data(
        self, correct_df: pd.DataFrame, output_df: pd.DataFrame
    ) -> List[Dict]:
        """データの値を比較する"""
        self.logger.critical("\n=== データ値の比較 ===")
        differences = []

        # 共通のカラムのみを比較
        common_columns = set(correct_df.columns) & set(output_df.columns)

        if not common_columns:
            self.logger.warning(
                "共通のカラムが存在しないため、データの比較ができません"
            )
            return differences

        total_differences = 0
        for column in common_columns:
            column_differences = 0
            for index in range(min(len(correct_df), len(output_df))):
                correct_value = correct_df.iloc[index][column]
                output_value = output_df.iloc[index][column]

                # 数値の場合は近似値も許容
                if pd.api.types.is_numeric_dtype(correct_df[column]):
                    if not pd.isna(correct_value) and not pd.isna(output_value):
                        if abs(correct_value - output_value) > 1e-10:
                            differences.append(
                                {
                                    "row": index
                                    + 1,  # 1-based indexing for user-friendly output
                                    "column": column,
                                    "correct_value": correct_value,
                                    "output_value": output_value,
                                }
                            )
                            column_differences += 1
                # 文字列やその他のデータ型の場合は完全一致を確認
                elif correct_value != output_value:
                    differences.append(
                        {
                            "row": index
                            + 1,  # 1-based indexing for user-friendly output
                            "column": column,
                            "correct_value": correct_value,
                            "output_value": output_value,
                        }
                    )
                    column_differences += 1

            if column_differences > 0:
                self.logger.warning(
                    f"カラム '{column}' で {column_differences} 件の不一致を検出"
                )
                total_differences += column_differences
            else:
                self.logger.info(f"✓ カラム '{column}' のデータは一致")

        if total_differences > 0:
            self.logger.critical("\n=== 不一致の詳細 ===")
            for diff in differences:
                self.logger.warning(
                    f"行 {diff['row']}, カラム '{diff['column']}':"
                    f"\n    - 正解値: {diff['correct_value']}"
                    f"\n    - 出力値: {diff['output_value']}"
                )

        return differences

    def compare_csvs(self) -> Dict:
        """CSVファイルの比較を実行する"""
        try:
            # タイトルの出力
            self.logger.critical("\n==========================================")
            self.logger.critical("        CSV比較レポート                    ")
            self.logger.critical("==========================================\n")

            # CSVファイルの読み込み
            correct_df, output_df = self.load_csv_files()

            # 構造の比較
            structure_results = self.compare_structure(correct_df, output_df)

            # データの比較
            data_differences = self.compare_data(correct_df, output_df)

            # 結果をまとめる
            comparison_results = {
                "structure": structure_results,
                "data_differences": data_differences,
                "is_identical": len(data_differences) == 0
                and structure_results["columns_match"]
                and structure_results["row_count_match"],
            }

            # 最終結果の出力
            self.logger.critical("\n=== 最終結果 ===")
            if comparison_results["is_identical"]:
                self.logger.info("✓ 両CSVファイルは完全に一致しています")
            else:
                self.logger.warning("両CSVファイルには差異があります")

            self.logger.critical("\n==========================================\n")

            return comparison_results

        except Exception as e:
            self.logger.error(f"比較処理中にエラーが発生しました: {str(e)}")
            raise


def main():
    try:
        comparator = CSVComparator()
        comparator.compare_csvs()

    except Exception as e:
        logging.error(f"プログラムの実行中にエラーが発生しました: {str(e)}")


if __name__ == "__main__":
    main()
