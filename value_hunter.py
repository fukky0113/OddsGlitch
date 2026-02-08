#!/usr/bin/env python3
"""
Value Hunter — 競馬バリュー分析ツール

概要:
  output/result.json を入力として、各出走馬のスコア・Gap・評価ランク(S/A/B/C)
  を算出し、バリュー（市場に対して過小評価されている馬）を検出する。

入力: output/result.json
出力:
  - コンソール: 評価一覧テーブル
  - JSON:       output/value_hunter_result.json

使い方:
  python value_hunter.py                           # デフォルト入力 output/result.json
  python value_hunter.py output/result.json         # 位置引数で入力ファイル指定
  python value_hunter.py -i output/result.json    # -i で入力指定
  python value_hunter.py output/result.json -o output/vh_result.json
"""

from __future__ import annotations

import json
import sys
import argparse
import unicodedata
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

# ============================================================
# 設定
# ============================================================

DEFAULT_INPUT = "output/result.json"
DEFAULT_OUTPUT = "output/value_hunter_result.json"

# 着順 → ポイント (1着=100 … 10着以下は段階的に低下)
POSITION_POINTS: dict[int, float] = {
    1: 100, 2: 90, 3: 80, 4: 65, 5: 55,
    6: 45,  7: 35, 8: 25, 9: 15, 10: 10,
}

# 走順 → 重み (run=1 が直近)
RECENCY_WEIGHTS: dict[int, float] = {
    1: 1.0, 2: 0.8, 3: 0.6, 4: 0.4, 5: 0.2,
}

# スコア配分
WEIGHT_FORM   = 0.30   # 着順フォーム
WEIGHT_LAST3F = 0.30   # 上がり3F
WEIGHT_UPSET  = 0.20   # 人気以上の好走力
WEIGHT_VENUE  = 0.20   # コース適性

# 評価ランク閾値
RANK_S_GAP = 4
RANK_A_GAP = 2
RANK_B_GAP = 0


# ============================================================
# データクラス
# ============================================================

@dataclass
class HorseEvaluation:
    """1頭分の評価結果"""
    number: int
    horse_name: str
    jockey: str
    odds: Optional[float]
    popularity: Optional[int]
    form_score: float = 0.0
    last3f_score: float = 0.0
    upset_score: float = 0.0
    venue_score: float = 0.0
    total_score: float = 0.0
    ability_rank: int = 0
    gap: int = 0
    evaluation: str = "C"
    past_race_count: int = 0


# ============================================================
# 入力読み込み
# ============================================================

def load_input(path: str) -> dict:
    """result.json を読み込み、最低限のバリデーションを行う。"""
    p = Path(path)
    if not p.exists():
        print(f"エラー: 入力ファイルが見つかりません: {path}", file=sys.stderr)
        sys.exit(1)
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    for key in ("race_id", "race", "horses"):
        if key not in data:
            print(f"エラー: 入力JSONに必須キー '{key}' がありません", file=sys.stderr)
            sys.exit(1)
    if not data["horses"]:
        print("エラー: horses 配列が空です", file=sys.stderr)
        sys.exit(1)
    return data


# ============================================================
# スコア算出
# ============================================================

def _position_points(pos: Optional[int]) -> float:
    """着順をポイントに変換する。"""
    if pos is None or pos <= 0:
        return 0
    return POSITION_POINTS.get(pos, max(5, 110 - pos * 10))


def calc_form_score(past_races: list[dict]) -> float:
    """着順ベースのフォームスコア（0–100）。

    直近の走ほど高い重みを付けた加重平均。
    """
    if not past_races:
        return 0.0
    weighted_sum = 0.0
    weight_total = 0.0
    for pr in past_races:
        run = pr.get("run", 1)
        w = RECENCY_WEIGHTS.get(run, 0.2)
        pts = _position_points(pr.get("position"))
        weighted_sum += pts * w
        weight_total += w
    return weighted_sum / weight_total if weight_total > 0 else 0.0


def calc_last3f_score(past_races: list[dict]) -> float:
    """上がり3Fベースのスコア（0–100）。

    上がりが速い（数値が小さい）ほどスコアが高い。
    33秒=100, 42秒=0 のスケール。
    """
    values: list[float] = []
    for pr in past_races:
        try:
            v = float(pr.get("last_3f", 0))
            if v > 0:
                values.append(v)
        except (ValueError, TypeError):
            pass
    if not values:
        return 0.0
    # 直近を重視した加重平均
    weighted_sum = 0.0
    weight_total = 0.0
    for pr in past_races:
        try:
            v = float(pr.get("last_3f", 0))
            if v <= 0:
                continue
        except (ValueError, TypeError):
            continue
        run = pr.get("run", 1)
        w = RECENCY_WEIGHTS.get(run, 0.2)
        weighted_sum += v * w
        weight_total += w
    if weight_total == 0:
        return 0.0
    avg = weighted_sum / weight_total
    return max(0.0, min(100.0, (42.0 - avg) / (42.0 - 33.0) * 100.0))


def calc_upset_score(past_races: list[dict]) -> float:
    """人気以上の好走実績スコア（0–100）。

    各レースで「人気順位 > 着順」（＝期待以上の好走）だった差分を集計。
    平均差 3 以上で満点。
    """
    if not past_races:
        return 0.0
    total_bonus = 0.0
    count = 0
    for pr in past_races:
        pop = pr.get("popularity")
        pos = pr.get("position")
        if pop and pos and pop > 0 and pos > 0:
            diff = pop - pos  # 正=人気以上の好走
            total_bonus += max(0.0, float(diff))
            count += 1
    if count == 0:
        return 0.0
    avg_bonus = total_bonus / count
    return min(100.0, avg_bonus / 3.0 * 100.0)


def calc_venue_score(past_races: list[dict], current_venue: str) -> float:
    """コース適性スコア（0–100）。

    同コースでの好走実績をもとに算出。実績がなければ経験数で基礎点。
    """
    if not past_races or not current_venue:
        return 0.0
    venue_races = [pr for pr in past_races if pr.get("venue") == current_venue]
    if not venue_races:
        # 同コース実績なし → 経験数に応じた基礎点
        return min(100.0, len(past_races) * 12.0)
    # 同コースでの着順ポイント平均
    pts_sum = sum(_position_points(pr.get("position")) for pr in venue_races)
    avg_pts = pts_sum / len(venue_races)
    score = avg_pts  # 0–100 のまま
    # 実績件数ボーナス（複数回好走しているなら加点）
    score = min(100.0, score + len(venue_races) * 5.0)
    return score


# ============================================================
# 評価（Gap・ランク）
# ============================================================

def evaluate_horses(data: dict) -> list[HorseEvaluation]:
    """全馬のスコア・Ability Rank・Gap・評価ランクを算出する。"""
    race = data.get("race", {})
    horses = data.get("horses", [])
    current_venue = race.get("venue", "")

    evals: list[HorseEvaluation] = []
    for h in horses:
        past = h.get("past_races", [])

        form   = calc_form_score(past)
        last3f = calc_last3f_score(past)
        upset  = calc_upset_score(past)
        venue  = calc_venue_score(past, current_venue)

        total = (
            form   * WEIGHT_FORM
            + last3f * WEIGHT_LAST3F
            + upset  * WEIGHT_UPSET
            + venue  * WEIGHT_VENUE
        )

        ev = HorseEvaluation(
            number=h.get("number", 0),
            horse_name=h.get("horse_name", ""),
            jockey=h.get("jockey", ""),
            odds=h.get("odds"),
            popularity=h.get("popularity"),
            form_score=round(form, 1),
            last3f_score=round(last3f, 1),
            upset_score=round(upset, 1),
            venue_score=round(venue, 1),
            total_score=round(total, 1),
            past_race_count=len(past),
        )
        evals.append(ev)

    # --- Ability Rank (total_score 降順) ---
    sorted_by_score = sorted(evals, key=lambda e: e.total_score, reverse=True)
    for rank, ev in enumerate(sorted_by_score, 1):
        ev.ability_rank = rank

    # --- Gap & Evaluation Rank ---
    avg_score = sum(e.total_score for e in evals) / len(evals) if evals else 0.0

    for ev in evals:
        # Gap = 人気順位 − 能力順位  (正=市場が過小評価)
        if ev.popularity is not None and ev.popularity > 0:
            ev.gap = ev.popularity - ev.ability_rank
        else:
            ev.gap = 0

        # 評価ランク
        if ev.gap >= RANK_S_GAP and ev.total_score >= avg_score:
            ev.evaluation = "S"
        elif ev.gap >= RANK_A_GAP and ev.total_score >= avg_score * 0.8:
            ev.evaluation = "A"
        elif ev.gap >= RANK_B_GAP:
            ev.evaluation = "B"
        else:
            ev.evaluation = "C"

    return evals


# ============================================================
# 表示ユーティリティ
# ============================================================

def _east_asian_width(text: str) -> int:
    """全角文字を幅2、半角を幅1として文字列の表示幅を返す。"""
    width = 0
    for ch in text:
        eaw = unicodedata.east_asian_width(ch)
        width += 2 if eaw in ("F", "W", "A") else 1
    return width


def _pad(text: str, width: int) -> str:
    """表示幅を考慮して右パディングする。"""
    diff = width - _east_asian_width(text)
    return text + " " * max(0, diff)


# ============================================================
# 出力
# ============================================================

EVAL_MARK = {"S": "★", "A": "◎", "B": "○", "C": "△"}
RANK_ORDER = {"S": 0, "A": 1, "B": 2, "C": 3}


def print_header(data: dict) -> None:
    """レースヘッダーを表示する。"""
    race = data.get("race", {})
    print()
    print("=" * 78)
    print("  Value Hunter — バリュー分析結果")
    print(f"  レース: {race.get('race_name', '')}  "
          f"{race.get('venue', '')} {race.get('race_date', '')}")
    print(f"  {race.get('course_type', '')}{race.get('distance', '')}m  "
          f"馬場:{race.get('track_condition', '')}  "
          f"天候:{race.get('weather', '')}")
    print("=" * 78)
    print()


def print_table(evals: list[HorseEvaluation]) -> None:
    """評価テーブルを表示する。"""
    # ヘッダー
    hdr = (f"{'番':>3}  {_pad('馬名', 18)}  {_pad('騎手', 8)}"
           f"  {'ｵｯｽﾞ':>6}  {'人気':>4}  {'ｽｺｱ':>5}"
           f"  {'能力':>4}  {'Gap':>4}  {'評価':>4}")
    print(hdr)
    print("-" * 78)

    # 評価順にソート (S→A→B→C, 同ランクは Gap 降順)
    sorted_evals = sorted(
        evals,
        key=lambda e: (RANK_ORDER.get(e.evaluation, 9), -e.gap, -e.total_score),
    )

    for ev in sorted_evals:
        odds_s = f"{ev.odds:.1f}" if ev.odds is not None else "---.-"
        pop_s  = f"{ev.popularity}" if ev.popularity is not None else "-"
        gap_s  = f"+{ev.gap}" if ev.gap > 0 else str(ev.gap)
        mark   = EVAL_MARK.get(ev.evaluation, " ")

        line = (f"{ev.number:>3}  {_pad(ev.horse_name, 18)}"
                f"  {_pad(ev.jockey, 8)}"
                f"  {odds_s:>6}  {pop_s:>4}  {ev.total_score:>5.1f}"
                f"  {ev.ability_rank:>4}  {gap_s:>4}"
                f"  {mark}{ev.evaluation}")
        print(line)

    print()


def print_detail(evals: list[HorseEvaluation]) -> None:
    """スコア内訳を表示する。"""
    print("--- スコア内訳 ---")
    hdr = (f"{'番':>3}  {_pad('馬名', 18)}"
           f"  {'Form':>5}  {'3F':>5}  {'穴力':>5}  {'適性':>5}"
           f"  {'合計':>5}  {'走数':>4}")
    print(hdr)
    print("-" * 72)

    sorted_evals = sorted(evals, key=lambda e: e.ability_rank)
    for ev in sorted_evals:
        line = (f"{ev.number:>3}  {_pad(ev.horse_name, 18)}"
                f"  {ev.form_score:>5.1f}  {ev.last3f_score:>5.1f}"
                f"  {ev.upset_score:>5.1f}  {ev.venue_score:>5.1f}"
                f"  {ev.total_score:>5.1f}  {ev.past_race_count:>4}")
        print(line)
    print()


def print_summary(evals: list[HorseEvaluation]) -> None:
    """バリュー注目馬のサマリーを表示する。"""
    s_horses = [e for e in evals if e.evaluation == "S"]
    a_horses = [e for e in evals if e.evaluation == "A"]

    print("=" * 78)
    print("  バリュー注目馬")
    print("=" * 78)
    if s_horses:
        for e in s_horses:
            odds_s = f"{e.odds:.1f}" if e.odds is not None else "---"
            print(f"  ★ S評価  {e.number}番 {e.horse_name}"
                  f"  (オッズ {odds_s} / 人気 {e.popularity}番人気"
                  f" → 能力 {e.ability_rank}位, Gap +{e.gap})")
    if a_horses:
        for e in a_horses:
            odds_s = f"{e.odds:.1f}" if e.odds is not None else "---"
            print(f"  ◎ A評価  {e.number}番 {e.horse_name}"
                  f"  (オッズ {odds_s} / 人気 {e.popularity}番人気"
                  f" → 能力 {e.ability_rank}位, Gap +{e.gap})")
    if not s_horses and not a_horses:
        print("  明確なバリュー馬は検出されませんでした。")
    print()


def print_results(data: dict, evals: list[HorseEvaluation]) -> None:
    """コンソールに全結果を表示する。"""
    print_header(data)
    print_table(evals)
    print_detail(evals)
    print_summary(evals)


# ============================================================
# JSON 出力
# ============================================================

def save_json(data: dict, evals: list[HorseEvaluation], output_path: str) -> None:
    """評価結果を JSON ファイルに保存する。"""
    race = data.get("race", {})
    result = {
        "race_id": data.get("race_id", ""),
        "race_name": race.get("race_name", ""),
        "venue": race.get("venue", ""),
        "race_date": race.get("race_date", ""),
        "course_type": race.get("course_type", ""),
        "distance": race.get("distance"),
        "field_average_score": round(
            sum(e.total_score for e in evals) / len(evals), 1
        ) if evals else 0,
        "evaluations": sorted(
            [asdict(ev) for ev in evals],
            key=lambda d: (RANK_ORDER.get(d["evaluation"], 9),
                           -d["gap"], -d["total_score"]),
        ),
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"結果を保存しました: {out}")


# ============================================================
# CLI
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Value Hunter — 競馬バリュー分析ツール",
        epilog="例: python value_hunter.py output/result.json"
               " または python value_hunter.py -i output/result.json -o output/vh.json",
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default=None,
        help="入力JSONファイルパス（位置引数で指定可能）",
    )
    parser.add_argument(
        "-i", "--input",
        default=None,
        help=f"入力JSONファイルパス（-i で指定する場合。未指定時は上記位置引数またはデフォルト {DEFAULT_INPUT}）",
    )
    parser.add_argument(
        "-o", "--output", default=DEFAULT_OUTPUT,
        help=f"出力JSONファイルパス (デフォルト: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--json-only", action="store_true",
        help="JSON出力のみ（コンソール表示なし）",
    )
    args = parser.parse_args()

    # 入力パス: 位置引数 > -i/--input > デフォルト
    input_path = args.input_file or args.input or DEFAULT_INPUT

    # 入力読み込み
    data = load_input(input_path)

    # 評価実行
    evals = evaluate_horses(data)

    # コンソール表示
    if not args.json_only:
        print_results(data, evals)

    # JSON保存
    save_json(data, evals, args.output)


if __name__ == "__main__":
    main()
