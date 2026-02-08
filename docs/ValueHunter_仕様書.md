# Value Hunter 仕様書

**対象モジュール**: `value_hunter.py`  
**版**: 1.1  
**入力**: `output/result.json`（OddsGlitch 出力形式）。コマンドラインで位置引数または `-i` により指定可能。

---

## 1. 概要

### 1.1 目的

競馬の「バリュー馬」を検出するための分析ツールである。  
入力JSON（レース1件分の出走馬・過去走・オッズ・人気）をもとに、各馬の**能力スコア**・**能力順位**・**人気との差（Gap）**・**評価ランク（S/A/B/C）**を算出し、市場に対して過小評価されている馬を抽出する。

### 1.2 スコープ

- **入力**: `output/result.json` と同一スキーマのJSONファイルのみ。ネット取得・API呼び出しは行わない。
- **出力**: コンソール表示（評価テーブル・スコア内訳・注目馬サマリー）および JSON ファイル。

---

## 2. 入力仕様

### 2.1 入力ファイル

| 項目 | 内容 |
|------|------|
| デフォルトパス | `output/result.json` |
| 形式 | JSON（UTF-8） |
| 指定方法 | **位置引数**（第1引数）または CLI オプション `-i` / `--input`（後述） |

### 2.2 必須キー

入力JSONは次のトップレベルキーを**必須**として持つこと。

| キー | 型 | 説明 |
|------|-----|------|
| `race_id` | string | レース識別子 |
| `race` | object | レース基本情報（後述） |
| `horses` | array | 出走馬の配列（1件以上） |

上記のいずれかが欠けている場合、または `horses` が空配列の場合、エラーメッセージを stderr に出力し **exit code 1** で終了する。

### 2.3 入力スキーマ（参照用）

#### トップレベル

- `source_url` (string, 任意)
- `race_id` (string, 必須)
- `race` (object, 必須)
- `race_info` (object, 任意)
- `horses` (array, 必須)

#### race オブジェクト（本ツールで参照する項目）

| キー | 型 | 用途 |
|------|-----|------|
| `race_name` | string | ヘッダー表示 |
| `venue` | string | **コース適性スコア（Venue Score）の算出に使用** |
| `race_date` | string | ヘッダー表示 |
| `course_type` | string | ヘッダー表示 |
| `distance` | number | ヘッダー表示 |
| `track_condition` | string | ヘッダー表示 |
| `weather` | string | ヘッダー表示 |

#### horses 配列の要素（1頭分）

| キー | 型 | 用途 |
|------|-----|------|
| `number` | number | 馬番（表示・出力） |
| `horse_name` | string | 馬名（表示・出力） |
| `jockey` | string | 騎手名（表示・出力） |
| `odds` | number or null | オッズ（表示・出力） |
| `popularity` | number or null | **Gap 算出**（人気順位として使用） |
| `past_races` | array | **全スコア算出**の元データ |

#### past_races の要素（1走分）

| キー | 型 | 用途 |
|------|-----|------|
| `run` | number | 何走前か（1=直近）。**重み付けに使用** |
| `date` | string | 本ツールでは未使用 |
| `venue` | string | **Venue Score**（今回の race.venue と一致するか） |
| `position` | number | **Form Score / Venue Score**（着順ポイント） |
| `time` | string | 本ツールでは未使用 |
| `last_3f` | string | **Last3F Score**（上がり3F 秒数） |
| `popularity` | number | **Upset Score**（人気以上の好走判定） |

### 2.4 欠損・null の扱い

- `odds` / `popularity` が null または欠損: 表示では "---.-" / "-"、Gap 算出時は **popularity を 0 扱いとし Gap=0**。
- `past_races` が空: 全スコア 0、能力順位は他馬との相対で決定。
- `last_3f` が数値化できない: その走は Last3F 計算から除外。
- `position` が null/0: 着順ポイント 0。

---

## 3. 処理仕様

### 3.1 処理フロー

1. **入力読み込み** … 指定パスからJSONを読む。必須キー・horses 非空をチェック。
2. **スコア算出** … 各馬ごとに Form / Last3F / Upset / Venue の4スコアを算出し、重み付き合計で **Total Score** を算出。
3. **Ability Rank 付与** … Total Score の**降順**で 1, 2, 3, … の順位を付与（同点の扱いは実装依存）。
4. **Gap 算出** … 各馬について `Gap = popularity - ability_rank`。popularity が null/0 の場合は Gap=0。
5. **評価ランク付与** … Gap と Total Score およびフィールド平均に基づき S/A/B/C を付与。
6. **出力** … コンソール表示（オプション）および JSON 保存。

### 3.2 定数一覧（スコア・ランク用）

| 定数名 | 値 | 説明 |
|--------|-----|------|
| `DEFAULT_INPUT` | `"output/result.json"` | デフォルト入力パス |
| `DEFAULT_OUTPUT` | `"output/value_hunter_result.json"` | デフォルト出力JSONパス |
| `POSITION_POINTS` | 1着=100, 2=85, 3=75, 4=65, 5=55, 6=45, 7=35, 8=25, 9=15, 10=10 | 着順→ポイント |
| `RECENCY_WEIGHTS` | run1=1.0, 2=0.8, 3=0.6, 4=0.4, 5=0.2 | 走順→重み（直近重視） |
| `WEIGHT_FORM` | 0.40 | Form Score の合計に対する重み |
| `WEIGHT_LAST3F` | 0.25 | Last3F Score の重み |
| `WEIGHT_UPSET` | 0.20 | Upset Score の重み |
| `WEIGHT_VENUE` | 0.15 | Venue Score の重み |
| `RANK_S_GAP` | 4 | S評価の Gap 閾値（以上） |
| `RANK_A_GAP` | 2 | A評価の Gap 閾値（以上） |
| `RANK_B_GAP` | 0 | B評価の Gap 閾値（以上） |

着順が 11 着以下の場合のポイントは `max(5, 110 - position * 10)` で算出。  
run が 1〜5 以外の場合は重み 0.2 を使用。

### 3.3 各スコアの算出式

#### Form Score（0〜100）

- 各過去走の `position` を `POSITION_POINTS` でポイント化（未定義は上記の線形式）。
- 各走に `RECENCY_WEIGHTS[run]` を掛けた加重平均を算出。
- 過去走が 0 件の場合は 0。

#### Last3F Score（0〜100）

- 各過去走の `last_3f` を数値化し、`RECENCY_WEIGHTS[run]` で加重平均した秒数を求める。
- 変換式: `(42 - avg_sec) / (42 - 33) * 100` を 0〜100 にクリップ。  
  - 33秒 → 100、42秒 → 0 のスケール。
- 有効な last_3f が 0 件の場合は 0。

#### Upset Score（0〜100）

- 各過去走について `diff = popularity - position`（人気順位 − 着順）を計算。diff > 0 のとき「人気以上の好走」。
- 有効な走のみで `avg_bonus = sum(max(0, diff)) / count` を算出。
- `min(100, avg_bonus / 3 * 100)` を Upset Score とする（平均差 3 で満点）。

#### Venue Score（0〜100）

- `race.venue`（今回の開催場所）と一致する `past_races` の要素を抽出。
- **同コース実績あり**: それらの着順を `POSITION_POINTS` でポイント化した平均に、`len(venue_races) * 5` のボーナスを加算。上限 100。
- **同コース実績なし**: `min(100, len(past_races) * 12)` を基礎点とする。

#### Total Score（0〜100 付近）

```
Total Score = Form×WEIGHT_FORM + Last3F×WEIGHT_LAST3F + Upset×WEIGHT_UPSET + Venue×WEIGHT_VENUE
```

小数点第1位で四捨五入して保持。

### 3.4 Ability Rank

- 全馬の Total Score を**降順**にソートし、1位から順に 1, 2, 3, … を付与。
- 同点の順序は実装依存（Python の sort の安定性に依存）。

### 3.5 Gap

```
Gap = popularity - ability_rank
```

- `popularity` が null または 0 の場合は **Gap = 0**。
- 正: 人気順位の方が能力順位より高い → 市場が過小評価（バリュー）。
- 負: 市場が過大評価。

### 3.6 評価ランク（S / A / B / C）

フィールド平均を `avg_score = sum(total_score) / 頭数` とする。

| ランク | 条件 |
|--------|------|
| **S** | `Gap >= RANK_S_GAP` かつ `total_score >= avg_score` |
| **A** | 上記を満たさず、`Gap >= RANK_A_GAP` かつ `total_score >= avg_score * 0.8` |
| **B** | 上記を満たさず、`Gap >= RANK_B_GAP` |
| **C** | 上記以外（Gap < 0） |

---

## 4. 出力仕様

### 4.1 コンソール出力（`--json-only` 未指定時）

1. **ヘッダー**  
   レース名・開催・日付・コース・距離・馬場・天候を 1 行〜数行で表示。

2. **評価一覧テーブル**  
   列: 馬番・馬名・騎手・オッズ・人気・スコア・能力順位・Gap・評価（S/A/B/C と記号 ★◎○△）。  
   行の並び: 評価ランク順（S→A→B→C）、同ランク内は Gap 降順・スコア降順。

3. **スコア内訳**  
   列: 馬番・馬名・Form・3F（Last3F）・穴力（Upset）・適性（Venue）・合計・走数。  
   行の並び: 能力順位（Ability Rank）の昇順。

4. **バリュー注目馬サマリー**  
   S評価・A評価の馬について、馬番・馬名・オッズ・人気・能力順位・Gap を列挙。  
   該当が 0 頭の場合は「明確なバリュー馬は検出されませんでした。」と表示。

コンソール出力では全角文字の表示幅を考慮したパディングを行う（East Asian Width）。

### 4.2 JSON 出力

- **保存先**: `-o` / `--output` で指定（デフォルト `output/value_hunter_result.json`）。
- 親ディレクトリが存在しない場合は作成する。
- エンコーディング: UTF-8。`ensure_ascii=False`, `indent=2` で出力。

#### ルートオブジェクト

| キー | 型 | 説明 |
|------|-----|------|
| `race_id` | string | 入力の race_id |
| `race_name` | string | 入力の race.race_name |
| `venue` | string | 入力の race.venue |
| `race_date` | string | 入力の race.race_date |
| `course_type` | string | 入力の race.course_type |
| `distance` | number | 入力の race.distance |
| `field_average_score` | number | 全馬の Total Score の平均（小数点第1位） |
| `evaluations` | array | 各馬の評価オブジェクトの配列（下記） |

#### evaluations の要素（1頭分）

| キー | 型 | 説明 |
|------|-----|------|
| `number` | number | 馬番 |
| `horse_name` | string | 馬名 |
| `jockey` | string | 騎手名 |
| `odds` | number or null | オッズ |
| `popularity` | number or null | 人気順位 |
| `form_score` | number | Form Score |
| `last3f_score` | number | Last3F Score |
| `upset_score` | number | Upset Score |
| `venue_score` | number | Venue Score |
| `total_score` | number | Total Score |
| `ability_rank` | number | 能力順位 |
| `gap` | number | Gap |
| `evaluation` | string | "S" / "A" / "B" / "C" |
| `past_race_count` | number | 過去走数 |

配列の並び順: 評価ランク（S→A→B→C）、同ランク内は Gap 降順・Total Score 降順。

---

## 5. CLI 仕様

### 5.1 引数一覧

| 種類 | 名前 | 短縮 | デフォルト | 説明 |
|------|------|------|------------|------|
| **位置引数** | `input_file` | - | なし（省略可） | 入力JSONファイルパス。省略時は `-i` またはデフォルトを使用 |
| オプション | `--input` | `-i` | なし | 入力JSONのパス（オプションで指定する場合） |
| オプション | `--output` | `-o` | `output/value_hunter_result.json` | 出力JSONのパス |
| オプション | `--json-only` | なし | false | 指定時はコンソール表示を行わず、JSON の保存のみ行う |

### 5.2 入力パスの決定順

入力に使用するファイルパスは、次の優先順位で決定する。

1. **位置引数** … 第1引数にファイルパスを書いた場合（例: `python value_hunter.py output/result.json`）
2. **`-i` / `--input`** … オプションで指定した場合
3. **デフォルト** … 上記がどちらも指定されていない場合に `output/result.json` を使用

### 5.3 使用例

```bash
python value_hunter.py                                    # デフォルト入力 output/result.json
python value_hunter.py output/result.json                  # 位置引数で入力指定
python value_hunter.py output/result.json -o output/vh.json
python value_hunter.py -i output/result.json -o output/vh_result.json
python value_hunter.py --json-only                         # JSON出力のみ（入力はデフォルト）
python value_hunter.py path/to/result.json --json-only
```

---

## 6. エラー・終了コード

| 状況 | 動作 | 終了コード |
|------|------|------------|
| 入力ファイルが存在しない | エラーメッセージを stderr に出力 | 1 |
| 必須キー（race_id / race / horses）の欠損 | エラーメッセージを stderr に出力 | 1 |
| horses が空配列 | エラーメッセージを stderr に出力 | 1 |
| 上記以外の正常終了 | JSON 保存し「結果を保存しました: …」を標準出力 | 0 |

JSON のパースエラーは未規定（Python の `json.load` の例外がそのまま上がる想定）。

---

## 7. データクラス（内部）

評価1頭分は `HorseEvaluation`  dataclass で保持する。

- `number`, `horse_name`, `jockey`, `odds`, `popularity` … 入力からコピー。
- `form_score`, `last3f_score`, `upset_score`, `venue_score`, `total_score` … 算出値（小数点第1位）。
- `ability_rank` … 1 始まりの能力順位。
- `gap` … 人気順位 − 能力順位。
- `evaluation` … "S" / "A" / "B" / "C"。
- `past_race_count` … 過去走数。

---

## 8. 変更履歴

| 版 | 日付 | 内容 |
|----|------|------|
| 1.0 | - | 初版（value_hunter.py 実装に基づく） |
| 1.1 | - | CLI: 入力ファイルを位置引数で指定可能に。入力パスの優先順位（位置引数 > -i > デフォルト）を明記。 |
