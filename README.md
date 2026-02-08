# OddsGlitch

netkeiba の競馬新聞ページからレース・出走馬データを取得し、規定JSONで出力するツール。あわせて **Value Hunter** により、オッズに対して過小評価されている馬（バリュー馬）をスコア・ランクで抽出する。

---

## 機能

| ツール | 説明 |
|--------|------|
| **OddsGlitch** (`main.py`) | レースIDを指定して netkeiba の競馬新聞（出走表・過去5走）を取得。オッズAPIで単勝オッズ・人気を取得し、1レース分のJSONを出力する。 |
| **Value Hunter** (`value_hunter.py`) | 上記JSONを入力に、各馬のフォーム・上がり3F・穴馬力・コース適性からスコアを算出。人気順位と能力順位の差（Gap）で S/A/B/C ランクを付け、バリュー馬を一覧表示・JSON出力する。 |

---

## 必要環境

- Python 3.10+
- 依存: `requests`, `beautifulsoup4`, `lxml`（標準のみで動作する部分は `value_hunter.py` のみ）

---

## セットアップ

```bash
git clone https://github.com/<your-username>/OddsGlitch.git
cd OddsGlitch
pip install -r requirements.txt
```

---

## 使い方

### 1. レースデータの取得（OddsGlitch）

```bash
# レースIDを指定してJSONを取得（出力は output/ に保存）
python main.py 202608020411 -o result.json

# 標準出力にのみ出す場合
python main.py 202608020411

# オッズ取得をスキップする場合
python main.py 202608020411 --no-odds -o result.json

# ローカルHTMLからパース（テスト用）
python main.py 202608020411 --local tests/fixtures/shutuba_past.html -o result.json
```

- **入力**: レースID（必須）、または `--local` でHTMLファイル
- **出力**: `output/<指定ファイル名>` または stdout。JSON形式は `output/result.json` 等を参照。

### 2. バリュー分析（Value Hunter）

```bash
# デフォルトで output/result.json を入力に分析
python value_hunter.py

# 入力ファイルを指定（位置引数 or -i）
python value_hunter.py output/result.json
python value_hunter.py -i output/result.json -o output/vh_result.json

# JSONのみ出力（コンソール表示なし）
python value_hunter.py output/result.json --json-only
```

- **入力**: OddsGlitch が出力したJSON（`output/result.json` 等）
- **出力**: コンソールに評価テーブル・スコア内訳・注目馬サマリー、および `output/value_hunter_result.json`（パスは `-o` で変更可）

---

## プロジェクト構成

```
OddsGlitch/
├── README.md
├── requirements.txt
├── config.py           # URL・タイムアウト等
├── main.py             # OddsGlitch CLI
├── value_hunter.py     # Value Hunter CLI
├── fetcher.py          # HTML・オッズ取得
├── builder.py          # JSON組み立て
├── schemas.py          # データ型定義
├── parser/
│   ├── race_info.py    # レース情報パース
│   ├── horses.py       # 出走馬・過去5走パース
│   └── utils.py
├── output/             # 出力JSONの格納先
└── docs/               # 作業全体像・仕様書・コード解説
```

---

## ドキュメント

- [作業全体像](docs/00_作業全体像.md) — 入力（result.json）と処理の流れ
- [Value Hunter 仕様書](docs/ValueHunter_仕様書.md) — スコア算出・Gap・ランクの定義
- [コード解説書](docs/コード解説書.md) — 実装の解説

---

## 注意事項

- netkeiba へのアクセスは利用規約・robots.txtに従ってください。連続リクエストは間隔を空けることを推奨します。
- オッズはレース前は未公開のことがあり、その場合は null になります。
- 本ツールの分析結果は投資・投票の助けとしてのみ利用し、自己責任でご利用ください。
