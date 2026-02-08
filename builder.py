"""JSON 組み立てモジュール

パーサの結果を RaceResult にまとめ、設計書準拠の JSON を生成する。
オッズ API の結果を各 Horse に紐付ける。
"""

from __future__ import annotations

from typing import Optional

from bs4 import BeautifulSoup

from fetcher import build_source_url
from parser.race_info import parse_race_info
from parser.horses import parse_horses
from schemas import Horse, RaceInfo, RaceResult


def _merge_odds(horses: list[Horse], odds_data: Optional[dict[str, dict]]) -> None:
    """オッズ API のデータを各 Horse にマージする (in-place)。

    Parameters
    ----------
    horses : list[Horse]
        パース済み出走馬リスト
    odds_data : dict | None
        fetch_odds() の返値。 { "01": {"odds": 39.6, "popularity": 10}, ... }
    """
    if not odds_data:
        return
    for horse in horses:
        key = f"{horse.number:02d}"
        entry = odds_data.get(key)
        if entry:
            horse.odds = entry.get("odds")
            horse.popularity = entry.get("popularity")


def build_race_result(
    soup: BeautifulSoup,
    race_id: str,
    odds_data: Optional[dict[str, dict]] = None,
) -> RaceResult:
    """パーサを呼び出して RaceResult を組み立てる。

    Parameters
    ----------
    soup : BeautifulSoup
        shutuba_past.html のパース済みツリー
    race_id : str
        レースID (例: "202608020411")
    odds_data : dict | None
        fetch_odds() の返値。None の場合、オッズ欄は空になる。

    Returns
    -------
    RaceResult
        設計書準拠の出力オブジェクト
    """
    race_basic = parse_race_info(soup)
    horses = parse_horses(soup)

    # オッズ API の結果を馬番で紐付け
    _merge_odds(horses, odds_data)

    return RaceResult(
        source_url=build_source_url(race_id),
        race_id=race_id,
        race=race_basic,
        race_info=RaceInfo(
            lap_prediction={},
            development={},
        ),
        horses=horses,
        poplar=[],
    )
