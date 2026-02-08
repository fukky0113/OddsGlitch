"""出走馬 & 過去5走成績 (Shutuba_Past5_Table) の抽出"""

from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup, Tag

from parser.utils import extract_horse_id, normalize_text
from schemas import Horse, PastRace


# ---------------------------------------------------------------------------
# 過去走セル (td.Past) の解析
# ---------------------------------------------------------------------------

def _parse_past_cell(td: Tag, run_index: int) -> PastRace | None:
    """1つの過去走セル (td.Past) を PastRace に変換する。

    Parameters
    ----------
    td : Tag
        class="Past ..." を持つ <td> 要素
    run_index : int
        何走前か (1=前走, 2=2走前, ...)

    Returns
    -------
    PastRace | None
        抽出できなければ None
    """
    data_item = td.select_one("div.Data_Item")
    if not data_item:
        return None

    date: Optional[str] = None
    venue: Optional[str] = None
    position: Optional[int] = None
    time_str: Optional[str] = None
    last_3f: Optional[str] = None
    popularity: Optional[int] = None

    # --- Data01: 日付・場所・着順 ---
    data01 = data_item.select_one("div.Data01")
    if data01:
        # 最初の span: "2025.11.24\xa0東京"
        first_span = data01.find("span", class_=lambda c: c is None or "Num" not in c)
        if first_span:
            raw = normalize_text(first_span.get_text())
            parts = raw.split()
            if parts:
                date = parts[0]  # "2025.11.24"
            if len(parts) >= 2:
                venue = parts[1]  # "東京"

        # span.Num: 着順
        num_span = data01.select_one("span.Num")
        if num_span:
            num_text = normalize_text(num_span.get_text())
            try:
                position = int(num_text)
            except (ValueError, TypeError):
                position = None

    # --- Data05: コース / 走破タイム / 馬場 ---
    data05 = data_item.select_one("div.Data05")
    if data05:
        text05 = normalize_text(data05.get_text())
        # 走破タイム: "1:46.0" のパターン
        m_time = re.search(r"(\d:\d{2}\.\d)", text05)
        if m_time:
            time_str = m_time.group(1)

    # --- Data03: 頭数・馬番・人気・騎手・斤量 ---
    # 例: "12頭 8番 5人 マーカンド 56.0"
    data03 = data_item.select_one("div.Data03")
    if data03:
        text03 = normalize_text(data03.get_text())
        m_pop = re.search(r"(\d+)人", text03)
        if m_pop:
            try:
                popularity = int(m_pop.group(1))
            except (ValueError, TypeError):
                pass

    # --- Data06: 通過順位 (上がり3F) 馬体重 ---
    data06 = data_item.select_one("div.Data06")
    if data06:
        text06 = normalize_text(data06.get_text())
        # 上がり3F: 最初の括弧内の小数 "(32.7)"
        m_3f = re.search(r"\((\d{2}\.\d)\)", text06)
        if m_3f:
            last_3f = m_3f.group(1)

    return PastRace(
        run=run_index,
        date=date,
        venue=venue,
        position=position,
        time=time_str,
        last_3f=last_3f,
        popularity=popularity,
    )


# ---------------------------------------------------------------------------
# 馬1頭 (tr.HorseList) の解析
# ---------------------------------------------------------------------------

def _parse_horse_row(tr: Tag) -> Horse | None:
    """テーブルの1行 (tr.HorseList) を Horse に変換する。"""

    # --- 馬番 ---
    # class が厳密に "Waku" の td (Waku1, Waku2 等の枠番は除外)
    waku_tds = tr.find_all("td", class_="Waku")
    if not waku_tds:
        return None
    try:
        number = int(normalize_text(waku_tds[0].get_text()))
    except (ValueError, TypeError):
        return None

    # --- 馬名・horse_id ---
    horse_info_td = tr.find("td", class_="Horse_Info")
    horse_name = ""
    horse_id = ""
    if horse_info_td:
        horse02 = horse_info_td.select_one("div.Horse02")
        if horse02:
            a_tag = horse02.find("a")
            if a_tag:
                horse_name = normalize_text(a_tag.get_text())
                horse_id = extract_horse_id(a_tag.get("href", ""))

    if not horse_name:
        return None

    # --- 騎手名・斤量 ---
    jockey_name: Optional[str] = None
    weight: Optional[float] = None
    jockey_td = tr.find("td", class_="Jockey")
    if jockey_td:
        # 騎手名: <a> タグのテキスト
        jockey_a = jockey_td.find("a")
        if jockey_a:
            jockey_name = normalize_text(jockey_a.get_text())

        # 斤量: Barei でない <span> から数値を取得
        for span in jockey_td.find_all("span"):
            if "Barei" in (span.get("class") or []):
                continue
            text = normalize_text(span.get_text())
            try:
                weight = float(text)
                break
            except (ValueError, TypeError):
                continue

    # --- 過去走 (最大5つの td.Past) ---
    past_tds = tr.find_all("td", class_="Past")
    past_races: list[PastRace] = []
    for idx, past_td in enumerate(past_tds, start=1):
        pr = _parse_past_cell(past_td, run_index=idx)
        if pr is not None:
            past_races.append(pr)

    return Horse(
        number=number,
        horse_id=horse_id,
        horse_name=horse_name,
        jockey=jockey_name,
        weight=weight,
        past_races=past_races,
    )


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------

def parse_horses(soup: BeautifulSoup) -> list[Horse]:
    """BeautifulSoup から全出走馬の情報を抽出する。"""
    table = soup.find("table", class_="Shutuba_Past5_Table", id="sort_table")
    if not table:
        # id なしでもクラスで探す (フォールバック)
        table = soup.find("table", class_="Shutuba_Past5_Table")
    if not table:
        return []

    horses: list[Horse] = []
    for tr in table.find_all("tr", class_="HorseList"):
        horse = _parse_horse_row(tr)
        if horse is not None:
            horses.append(horse)

    # 馬番でソート
    horses.sort(key=lambda h: h.number)
    return horses
