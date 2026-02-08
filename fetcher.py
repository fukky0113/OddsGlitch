"""HTML / オッズ API 取得モジュール

shutuba_past.html を取得し BeautifulSoup ツリーを返す。
ページは EUC-JP エンコーディングで配信される。

オッズは netkeiba 内部 API (api_get_jra_odds.html) から JSON で取得する。
API レスポンス形式:
  {
    "status": "result",
    "data": {
      "official_datetime": "...",
      "odds": {
        "1": { "01": ["39.6", "", "10"], ... }   ← 単勝 [オッズ, _, 人気]
      }
    }
  }
"""

from __future__ import annotations

import sys
from typing import Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

import config


# ---------------------------------------------------------------------------
# URL ビルダー
# ---------------------------------------------------------------------------

def build_url(race_id: str) -> str:
    """race_id から shutuba_past.html の URL を組み立てる。"""
    params = urlencode({"race_id": race_id, "rf": "shutuba_submenu"})
    return f"{config.BASE_URL}?{params}"


def build_source_url(race_id: str) -> str:
    """出力 JSON に記載する source_url (newspaper.html) を組み立てる。"""
    params = urlencode({"race_id": race_id, "rf": "shutuba_submenu"})
    return f"{config.NEWSPAPER_URL}?{params}"


# ---------------------------------------------------------------------------
# HTML 取得
# ---------------------------------------------------------------------------

def fetch_html(race_id: str) -> BeautifulSoup:
    """指定 race_id のページを取得し、BeautifulSoup オブジェクトを返す。

    Parameters
    ----------
    race_id : str
        レースID (例: "202608020411")

    Returns
    -------
    BeautifulSoup
        パース済みの HTML ツリー

    Raises
    ------
    requests.HTTPError
        HTTP エラーが発生した場合
    """
    url = build_url(race_id)
    response = requests.get(
        url,
        headers=config.HEADERS,
        timeout=config.REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    # EUC-JP をバイト列から直接パースする
    soup = BeautifulSoup(
        response.content,
        "lxml",
        from_encoding=config.PAGE_ENCODING,
    )
    return soup


def fetch_html_from_file(filepath: str) -> BeautifulSoup:
    """ローカルの HTML ファイルからパースする (テスト・開発用)。"""
    with open(filepath, "rb") as f:
        raw = f.read()
    soup = BeautifulSoup(raw, "lxml", from_encoding=config.PAGE_ENCODING)
    return soup


# ---------------------------------------------------------------------------
# オッズ API 取得
# ---------------------------------------------------------------------------

def _build_odds_api_url(race_id: str) -> str:
    """オッズ API の URL を組み立てる。"""
    params = urlencode({"race_id": race_id, "type": "1"})
    return f"{config.ODDS_API_URL}?{params}"


def fetch_odds(race_id: str) -> Optional[dict[str, dict]]:
    """netkeiba オッズ API から単勝オッズ・人気を取得する。

    Parameters
    ----------
    race_id : str
        レースID

    Returns
    -------
    dict[str, dict] | None
        成功時: { "01": {"odds": 39.6, "popularity": 10}, ... }
        オッズ未公開・エラー時: None

        キーは馬番をゼロパディングした文字列 ("01"〜)。
    """
    url = _build_odds_api_url(race_id)
    try:
        response = requests.get(
            url,
            headers=config.HEADERS,
            timeout=config.REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"[WARN] オッズ API 取得失敗: {exc}", file=sys.stderr)
        return None

    # ステータス確認: "result" 以外はオッズ未公開
    if body.get("status") != "result":
        reason = body.get("reason", body.get("status", "unknown"))
        print(f"[INFO] オッズ未公開 (reason={reason})", file=sys.stderr)
        return None

    data = body.get("data")
    if not data or not isinstance(data, dict):
        return None

    # odds["1"] = 単勝オッズ
    win_odds_raw: dict = data.get("odds", {}).get("1", {})
    if not win_odds_raw:
        return None

    result: dict[str, dict] = {}
    for horse_num_str, values in win_odds_raw.items():
        # values = ["39.6", "", "10"]
        #           [odds,   _,  popularity]
        if not isinstance(values, list) or len(values) < 3:
            continue
        try:
            odds_val = float(values[0]) if values[0] else None
        except (ValueError, TypeError):
            odds_val = None
        try:
            pop_val = int(values[2]) if values[2] else None
        except (ValueError, TypeError):
            pop_val = None
        result[horse_num_str] = {"odds": odds_val, "popularity": pop_val}

    return result if result else None
