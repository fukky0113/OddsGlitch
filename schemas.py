"""出力JSONの型定義 (dataclass ベース)"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class PastRace:
    """過去走1レース分"""

    run: int  # セルのインデックス (1〜5)
    date: Optional[str] = None  # 実施日 例: "2025.11.24"
    venue: Optional[str] = None  # 競馬場名
    position: Optional[int] = None  # 着順
    time: Optional[str] = None  # 走破タイム 例: "1:46.0"
    last_3f: Optional[str] = None  # 上がり3ハロン 例: "32.7"
    popularity: Optional[int] = None  # 人気 (過去走時点)


@dataclass
class Horse:
    """出走馬1頭分"""

    number: int  # 馬番
    horse_id: str  # 10桁の数値ID
    horse_name: str  # 馬名
    jockey: Optional[str] = None  # 騎手名
    weight: Optional[float] = None  # 斤量
    odds: Optional[float] = None  # 単勝オッズ (現在)
    popularity: Optional[int] = None  # 人気順位 (現在)
    past_races: list[PastRace] = field(default_factory=list)


@dataclass
class RaceBasicInfo:
    """レース基本情報"""

    race_name: str = ""
    race_info_text: str = ""
    post_time: Optional[str] = None  # "HH:MM"
    course_type: Optional[str] = None  # "芝" or "ダ"
    distance: Optional[int] = None  # メートル
    track_condition: Optional[str] = None  # 良/稍/重/不
    weather: Optional[str] = None  # 晴/曇/雨/雪
    race_date: Optional[str] = None  # "YYYY/MM/DD"
    venue: Optional[str] = None  # "京都" 等


@dataclass
class RaceInfo:
    """設計書の race_info (空オブジェクト用)"""

    lap_prediction: dict = field(default_factory=dict)
    development: dict = field(default_factory=dict)


@dataclass
class RaceResult:
    """最終出力のルートオブジェクト"""

    source_url: str = ""
    race_id: str = ""
    race: RaceBasicInfo = field(default_factory=RaceBasicInfo)
    race_info: RaceInfo = field(default_factory=RaceInfo)
    horses: list[Horse] = field(default_factory=list)
    poplar: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
