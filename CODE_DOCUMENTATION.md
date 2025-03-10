# CODE_DOCUMENTATION.md

このドキュメントは、給与計算システムにおける以下の2つの主要ソースコードについて、その目的、構成、主要クラス・関数、及び処理の流れを詳細に説明しています。

- **llm-intent-analyzer-python.py**
- **payroll-python.py**

---

## 目次

- [CODE\_DOCUMENTATION.md](#code_documentationmd)
  - [目次](#目次)
  - [概要](#概要)
  - [llm-intent-analyzer-python.py](#llm-intent-analyzer-pythonpy)
    - [目的と概要](#目的と概要)
    - [主要クラスと関数](#主要クラスと関数)
      - [IntentType, ConversationContext, IntentAnalysisResult](#intenttype-conversationcontext-intentanalysisresult)
      - [LLMIntentAnalyzer クラス](#llmintentanalyzer-クラス)
      - [PayrollAgentIntentHandler クラス](#payrollagentintenthandler-クラス)
  - [payroll-python.py](#payroll-pythonpy)
    - [目的と概要](#目的と概要-1)
    - [データクラス定義](#データクラス定義)
      - [FileSummary, ValidationResult, CalculationSummary](#filesummary-validationresult-calculationsummary)
    - [タスク管理と計算処理](#タスク管理と計算処理)
      - [TaskManager クラス](#taskmanager-クラス)
      - [PayrollCalculator クラス](#payrollcalculator-クラス)
      - [PayrollAgent クラス](#payrollagent-クラス)
  - [まとめ](#まとめ)

---

## 概要

本システムは、給与計算に関連する各種タスクの自動化・管理を目的としています。  
- **llm-intent-analyzer-python.py** は、ユーザーの入力からその意図を解析するためのモジュールです。LLM（大規模言語モデル）を呼び出して、タスク開始、質問、ファイルアップロード、確認応答、メニューへの復帰などのインテントを抽出し、対話コンテキストを管理します。  
- **payroll-python.py** は、給与計算タスクの全体フローを管理するモジュールで、ファイルアップロード、タスク開始、計算処理、及び結果出力などの処理を実装しています。タスクの定義、入力ファイルのサマリー、計算結果のサマリー生成と実際の給与計算ロジックを含みます。

---

## llm-intent-analyzer-python.py

### 目的と概要

このモジュールは、ユーザーの入力メッセージからその意図（インテント）を抽出するために設計されています。  
- 会話の履歴や現在の状態を踏まえたプロンプトを生成し、LLM へ問い合わせることで、ユーザーの要求内容を JSON 形式で出力します。  
- また、抽出されたインテントに基づいて会話コンテキストを更新し、後続の処理（タスク開始、ファイルアップロードなど）のルーティングに利用されます。

### 主要クラスと関数

#### IntentType, ConversationContext, IntentAnalysisResult

- **IntentType (Enum)**  
  ユーザーの意図を表すために、以下の種類を定義しています:
  - `TASK_START`
  - `QUESTION`
  - `FILE_UPLOAD`
  - `CONFIRMATION`
  - `RETURN_TO_MENU`
  - `UNKNOWN`

- **ConversationContext (dataclass)**  
  現在の会話状態を管理するためのデータクラス。  
  属性例:
  - `last_intent`: 最後に解析されたインテント
  - `current_task`: 現在のタスク（該当する場合）
  - `last_message`: 最後のメッセージの内容（JSON形式）
  - `conversation_state`: 会話の状態（初期値は "init"）

- **IntentAnalysisResult (dataclass)**  
  インテント解析の結果を保持するデータクラス。  
  属性例:
  - `intent_type`: 抽出されたインテント（IntentType 型）
  - `confidence`: インテントの信頼度（例: 0.9）
  - `params`: インテントに付随するパラメータ（例: task_name, query など）
  - `context`: 現在の会話コンテキスト

#### LLMIntentAnalyzer クラス

- **概要**  
  ユーザー入力と最近の会話履歴、現在の会話状態をもとに、LLM へ問い合わせるプロンプトを生成し、インテント解析を実行するクラスです。

- **主な処理の流れ**:
  1. **_create_prompt(user_input)**  
     ユーザー入力と過去の会話履歴（最大3件）を整形し、LLM への問い合わせ用プロンプトを生成します。  
     指示として、特定の形式（JSON）のレスポンスを求めます。
  2. **_call_llm(prompt)**  
     非同期で LLM API を呼び出すメソッド。ここではサンプルレスポンスを返すシミュレーションが実装されています。
  3. **_update_context(intent_result)**  
     解析結果に基づいて、`ConversationContext` を更新します。たとえば、タスク開始の場合は状態を "task_selection" に変更し、現在のタスク名を設定します。
  4. **analyze_intent(user_input)**  
     上記のプロンプト生成、LLM 呼び出し、レスポンスの JSON パース、コンテキスト更新、履歴への記録を順次実行し、`IntentAnalysisResult` を返します。

#### PayrollAgentIntentHandler クラス

- **概要**  
  給与計算エージェント向けのインテントハンドラです。  
  `LLMIntentAnalyzer` を利用してユーザーの入力からインテントを解析し、その結果に基づいて適切な処理を振り分けます。

- **主なメソッド**:
  - **handle_user_input(user_input)** (async)  
    ユーザー入力に対して `analyze_intent` を呼び出し、解析結果に基づいて以下の各ハンドラを実行:
    - **_handle_task_start**: タスク開始の場合、給与計算タスクの開始と必要ファイルの案内を返す。
    - **_handle_file_upload**: ファイルアップロードの指示に基づき、該当ファイルのアップロード受付メッセージを返す。
    - **_handle_confirmation**: ユーザーの確認応答に基づき、処理の継続または中断を返す。
    - **_handle_question**: 質問に対する回答（ここでは準備中メッセージ）を返す。
    - **_handle_return_to_menu**: メインメニューへの復帰メッセージを返す。

- **使用例**:  
  メイン関数 `main()` では、いくつかのサンプル入力（メニュー選択、ファイルアップロード、質問など）に対してハンドリングが実行され、システムからの返答が表示されます。

---

## payroll-python.py

### 目的と概要

`payroll-python.py` は、給与計算タスクの全体処理フローを管理するモジュールです。  
- タスクの定義、必要なファイルのアップロードとサマリー、給与計算ロジックの実行、及び結果出力までを担います。  
- ユーザーの操作に応じたタスク開始、ファイルアップロード、確認応答、計算実行などを非同期で処理します。

### データクラス定義

#### FileSummary, ValidationResult, CalculationSummary

- **FileSummary (dataclass)**  
  ファイルの概要情報を管理します。  
  属性:
  - `file_type`: ファイルの種類
  - `record_count`: レコード数
  - `target_year_month`: 対象年月（任意）
  - `warnings`: 注意事項リスト（初期化時に空リストに設定）
  - `details`: 追加の詳細情報（初期化時に空辞書に設定）

- **ValidationResult (dataclass)**  
  ファイル検証の結果を表し、妥当性、エラー、警告のリストを保持します。

- **CalculationSummary (dataclass)**  
  給与計算前のサマリー情報を保持します。  
  属性:
  - `target_year_month`: 対象年月
  - `employee_count`: 対象社員数
  - `department_count`: 部門数
  - `total_work_days`: 勤務日数
  - `overtime_hours`: 総残業時間
  - `special_cases`: 特殊なケース（注意事項等）

### タスク管理と計算処理

#### TaskManager クラス

- **概要**  
  タスクの定義やファイルアップロードの進捗管理、及び計算実行前のサマリー生成を行うクラスです。
- **主な機能**:
  - **start_task(task_type)**: 指定されたタスク（例: 給与計算）を開始し、必要なファイル情報を返す。
  - **handle_file_upload(file_type, file_path, validation_result, file_summary)**: アップロードされたファイルの情報を保存し、全ファイルが揃った場合に計算サマリーを生成する。
  - **generate_calculation_summary()**: 給与計算タスクにおけるサマリー情報（社員数、部門数、勤務日数、残業時間等）を生成する。
  - **get_special_cases()**: 各ファイルの警告情報を集約し、特殊ケースとして返す。

#### PayrollCalculator クラス

- **概要**  
  給与計算の実際のロジックを実装するクラスです。
- **主な機能**:
  - **calculate(task_type, files)**: タスク種類に応じた計算処理を実行し、結果ファイルのパスやサマリー情報を返す。
  - **_calculate_salary(files)**: 給与計算の場合、従業員マスタ、勤怠データ、手当マスタの CSV を読み込み、計算を実施した上で結果を Excel ファイルとして出力する。

#### PayrollAgent クラス

- **概要**  
  給与計算エージェントのメインクラスで、ユーザー入力の受付からタスク開始、ファイルアップロード、確認応答、計算実行までの一連の処理を統括します。
- **主な機能**:
  - **handle_user_input(input_text)** (async): ユーザー入力に基づき、LLM で意図解析（ここでは仮想の処理）を行い、タスク開始、ファイルアップロード、確認応答などの処理ルートに振り分ける。
  - **handle_confirmation(confirmed)** (async): ユーザーの確認応答を処理し、必要なファイルが揃っていれば計算処理を実行するか、確認メッセージを生成する。
  - **create_confirmation_message(summary)**: 計算前のサマリー情報を整形して、ユーザーに確認メッセージとして提示する。
  - **execute_calculation()** (async): 計算処理を実行し、結果ファイルのパスや処理結果のサマリーを返す。
  - **send_message(message)** (async): 実際の実装では WebSocket などでメッセージを送信するが、ここでは標準出力に表示する簡易実装。

- **使用例**:  
  メイン関数 `main()` により、サンプル入力（「給与計算を開始」、「従業員マスタをアップロード」、「はい」）に対するシステムの返答がデモンストレーションされます。

---

## まとめ

本ドキュメントでは、以下の2つのソースコードの設計と実装の概要を説明しました。

- **llm-intent-analyzer-python.py**  
  ユーザー入力から意図を抽出するためのプロンプト生成、LLM 呼び出し、レスポンスパース、会話コンテキスト更新などの処理を通じて、タスク開始、質問、ファイルアップロード、確認応答、メニュー復帰などのインテントを解析する仕組みを提供します。

- **payroll-python.py**  
  給与計算タスクの全体フロー（タスク開始、ファイルアップロード、計算前のサマリー生成、計算実行、結果出力）を管理するモジュールです。  
  タスク定義やファイルの概要情報、計算結果のサマリー生成など、実際の給与計算処理に必要なロジックを実装しています。

これらのモジュールは、給与計算の自動化・管理システムの中核を担い、ユーザーからの自然言語入力に基づく柔軟な処理ルートの振り分けと、実際の計算処理の実行を統合的に実現しています。将来的な拡張や保守の際は、本ドキュメントを参照して各モジュールの責務と処理の流れを把握してください。
