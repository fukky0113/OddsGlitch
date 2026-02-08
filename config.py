"""スクレイピング設定"""

# URL テンプレート
# newspaper.html には過去5走テーブルが無いため、shutuba_past.html を実際の取得先とする
BASE_URL = "https://race.netkeiba.com/race/shutuba_past.html"
NEWSPAPER_URL = "https://race.netkeiba.com/race/newspaper.html"

# オッズ API (単勝: type=1)
ODDS_API_URL = "https://race.netkeiba.com/api/api_get_jra_odds.html"

# リクエストヘッダー
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
}

# ページのエンコーディング
PAGE_ENCODING = "euc-jp"

# リクエスト間のインターバル (秒)
REQUEST_INTERVAL = 2.0

# リクエストタイムアウト (秒)
REQUEST_TIMEOUT = 30
