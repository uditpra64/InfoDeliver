## 入力パラメータ
- `staffcode`: スタッフコード    <!-- 必ずある -->

- `check_csv`: データフレーム    <!-- 一番目出力用ファイル -->
  - 含む列：`スタッフコード`,`健保（翌月）`, `介護（翌月）`, `厚年（翌月）`, `子育て拠出金（翌月）`, `退職日`（YYYY-MM-DD形式）<!-- `スタッフコード`必ずある、以外の処理中使う列は日付の場合日付の形式を追加してください -->
- `sikyu_csv`: データフレーム　<!-- オプショナルの場合、後に'(オプショナル)'をつけてください -->
  - 含む列：`スタッフコード`,`健保事業主負担`, `介護事業主負担`, `厚年事業主負担`, `子育拠出金`

## 処理内容
### 処理対象
- `sikyu_csv`の中で`スタッフコード`が入力パラメータの`staffcode`と一致する行　<!-- ここは出力ファイルの名前を変更する以外はかわらない。処理のロジックは当たる行を処理することです-->

### 処理規則
1. 今月退職の場合 <!-- ブランチある場合、そういうふうに書いてください -->
   - `健保事業主負担` + `健保（翌月）` <!-- シンプルに計算する列の名前とルール書いてください -->
   - `介護事業主負担` + `介護（翌月）` <!-- できるだけ曖昧な言葉を避けてください-->
   - `厚年事業主負担` + `厚年（翌月）`       <!-- 支給日に関わる場合、'今月'という言葉を使ってください-->
   - `子育拠出金` + `子育て拠出金（翌月）`
2. 先月退職の場合
   - `健保事業主負担` + 0
   - `介護事業主負担` + 0
   - `厚年事業主負担` + 0
   - `子育拠出金` + 0
3. その他の場合
   - 処理なし

## 出力
- 行の全項目をデータフレームとして出力 <!-- ここは出力ファイルの名前を変更する以外はかわらない -->
