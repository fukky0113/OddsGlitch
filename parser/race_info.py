"""レース基本情報 (RaceList_NameBox) の抽出"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from parser.utils import normalize_text
from schemas import RaceBasicInfo


# グレードアイコンクラス → テキストのマッピング
_GRADE_MAP: dict[str, str] = {
    "Icon_GradeType1": "G1",
    "Icon_GradeType2": "G2",
    "Icon_GradeType3": "G3",
}


def _detect_grade(name_box: Tag) -> str:
    """RaceName 内のアイコンクラスからグレードを判定する。"""
    race_name_tag = name_box.select_one("h1.RaceName")
    if not race_name_tag:
        return ""
    for span in race_name_tag.find_all("span", class_=True):
        classes = span.get("class", [])
        for cls in classes:
            if cls in _GRADE_MAP:
                return _GRADE_MAP[cls]
    return ""


def _extract_race_name(name_box: Tag) -> str:
    """レース名を取得し、グレード表記を付加する。"""
    race_name_tag = name_box.select_one("h1.RaceName")
    if not race_name_tag:
        return ""
    # h1 直下のテキストノードのみ取得 (子要素のアイコンテキストを除外)
    raw = race_name_tag.find(string=True, recursive=False)
    name = normalize_text(str(raw)) if raw else ""
    grade = _detect_grade(name_box)
    if grade:
        name = f"{name} ({grade})"
    return name


def _get_race_data01_text(name_box: Tag) -> str:
    """RaceData01 のテキストを取得する。"""
    data01 = name_box.select_one("div.RaceData01")
    if not data01:
        return ""
    return normalize_text(data01.get_text())


def _get_race_data02_spans(name_box: Tag) -> list[str]:
    """RaceData02 の各 span テキストをリストで返す。"""
    data02 = name_box.select_one("div.RaceData02")
    if not data02:
        return []
    return [normalize_text(s.get_text()) for s in data02.find_all("span")]


def _extract_post_time(text: str) -> str | None:
    m = re.search(r"(\d{1,2}:\d{2})", text)
    return m.group(1) if m else None


def _extract_course_type(text: str) -> str | None:
    if "芝" in text:
        return "芝"
    if "ダ" in text:
        return "ダ"
    return None


def _extract_distance(text: str) -> int | None:
    m = re.search(r"(\d{3,4})m", text)
    return int(m.group(1)) if m else None


def _extract_track_condition(text: str) -> str | None:
    m = re.search(r"馬場:(\S+)", text)
    return m.group(1) if m else None


def _extract_weather(text: str) -> str | None:
    m = re.search(r"天候:(\S+)", text)
    return m.group(1) if m else None


def _extract_race_date(soup: BeautifulSoup) -> str | None:
    """<title> タグから日付を抽出して YYYY/MM/DD に変換する。"""
    title = soup.title
    if not title:
        return None
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", title.get_text())
    if not m:
        return None
    return f"{m.group(1)}/{int(m.group(2)):02d}/{int(m.group(3)):02d}"


def _extract_venue(data02_spans: list[str]) -> str | None:
    """RaceData02 の第2 span (場所名) を返す。

    例: ["2回", "京都", "4日目", ...] → "京都"
    """
    if len(data02_spans) >= 2:
        return data02_spans[1]
    return None


def parse_race_info(soup: BeautifulSoup) -> RaceBasicInfo:
    """BeautifulSoup から RaceBasicInfo を抽出する。"""
    name_box = soup.select_one("div.RaceList_NameBox")
    if not name_box:
        return RaceBasicInfo()

    data01_text = _get_race_data01_text(name_box)
    data02_spans = _get_race_data02_spans(name_box)
    data02_text = " ".join(data02_spans)

    # race_info_text: RaceData01 と RaceData02 の結合テキスト
    race_info_text = f"{data01_text} / {data02_text}" if data02_text else data01_text

    return RaceBasicInfo(
        race_name=_extract_race_name(name_box),
        race_info_text=race_info_text,
        post_time=_extract_post_time(data01_text),
        course_type=_extract_course_type(data01_text),
        distance=_extract_distance(data01_text),
        track_condition=_extract_track_condition(data01_text),
        weather=_extract_weather(data01_text),
        race_date=_extract_race_date(soup),
        venue=_extract_venue(data02_spans),
    )
