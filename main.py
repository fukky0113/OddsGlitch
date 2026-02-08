#!/usr/bin/env python3
"""netkeiba 競馬新聞データ抽出エンジン — CLI エントリポイント

使い方
------
# race_id を指定して実行
python main.py 202608020411

# 出力ファイルを指定
python main.py 202608020411 -o output.json

# ローカル HTML ファイルからパース (テスト用)
python main.py 202608020411 --local tests/fixtures/shutuba_past.html
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import config
from builder import build_race_result
from fetcher import fetch_html, fetch_html_from_file, fetch_odds


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="netkeiba 競馬新聞ページからレース・出走馬データを抽出する",
    )
    parser.add_argument(
        "race_id",
        help="レースID (例: 202608020411)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="出力先ファイルパス (省略時は stdout)",
    )
    parser.add_argument(
        "--local",
        default=None,
        help="ローカルHTMLファイルからパース (テスト用)",
    )
    parser.add_argument(
        "--no-odds",
        action="store_true",
        default=False,
        help="オッズ API の取得をスキップする",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON インデント幅 (デフォルト: 2)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    race_id: str = args.race_id

    # HTML 取得
    if args.local:
        print(f"[INFO] ローカルファイルからパース: {args.local}", file=sys.stderr)
        soup = fetch_html_from_file(args.local)
    else:
        print(f"[INFO] ページ取得中: race_id={race_id}", file=sys.stderr)
        soup = fetch_html(race_id)
        print(f"[INFO] 取得完了", file=sys.stderr)

    # オッズ取得
    odds_data = None
    if not args.no_odds:
        print(f"[INFO] オッズ取得中...", file=sys.stderr)
        odds_data = fetch_odds(race_id)
        if odds_data:
            print(f"[INFO] オッズ取得完了 ({len(odds_data)}頭分)", file=sys.stderr)
        else:
            print(f"[INFO] オッズ未公開またはレース終了前", file=sys.stderr)

    # パース & JSON 組み立て
    result = build_race_result(soup, race_id, odds_data=odds_data)

    # 出力
    json_str = result.to_json(indent=args.indent)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"[INFO] 出力完了: {args.output}", file=sys.stderr)
    else:
        print(json_str)

    # サマリー
    print(
        f"[INFO] レース: {result.race.race_name} | "
        f"出走馬: {len(result.horses)}頭 | "
        f"日付: {result.race.race_date}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
