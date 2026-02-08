"""テキスト正規化・共通ユーティリティ"""

from __future__ import annotations

import re
import unicodedata


def normalize_text(text: str) -> str:
    """HTML 由来のテキストを正規化する。

    - 全角スペース → 半角スペース
    - \\xa0 (nbsp) → 半角スペース
    - 連続空白 → 単一スペース
    - 前後の空白を除去
    - Unicode NFKC 正規化
    """
    if not text:
        return ""
    # NFKC 正規化 (全角英数 → 半角, etc.)
    text = unicodedata.normalize("NFKC", text)
    # \xa0 (non-breaking space) や全角空白を半角スペースに
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    # 連続空白を単一スペースに
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_int(text: str) -> int | None:
    """文字列から最初の整数を抽出する。"""
    m = re.search(r"\d+", text or "")
    return int(m.group()) if m else None


def extract_float(text: str) -> float | None:
    """文字列から最初の浮動小数点数を抽出する。"""
    m = re.search(r"\d+\.\d+", text or "")
    return float(m.group()) if m else None


def extract_horse_id(href: str) -> str:
    """馬リンクの href から 10桁の horse_id を抽出する。

    例: "https://db.netkeiba.com/horse/2023106850" → "2023106850"
    """
    m = re.search(r"/horse/(\d{10})", href or "")
    return m.group(1) if m else ""
