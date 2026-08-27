"""CSV row normalizers for staged NSE archives."""

import logging
from datetime import date, datetime

from powernse.schemas import FoRow, IndexRow, OhlcRow

logger = logging.getLogger(__name__)


class BhavcopyRow:
    """Normalize one legacy or UDIFF bhavcopy CSV row into an OhlcRow."""

    SYMBOL_KEYS = ("SYMBOL", "TckrSymb")
    SERIES_KEYS = ("SERIES", "SctySrs")
    OPEN_KEYS = ("OPEN", "OpnPric")
    HIGH_KEYS = ("HIGH", "HghPric")
    LOW_KEYS = ("LOW", "LwPric")
    CLOSE_KEYS = ("CLOSE", "ClsPric")
    VOLUME_KEYS = ("TOTTRDQTY", "TtlTradgVol")
    ISIN_KEYS = ("ISIN",)
    DATE_KEYS = ("TradDt", "TIMESTAMP")

    @classmethod
    def from_row(cls, row: dict[str, str], *, trade_date: date) -> OhlcRow | None:
        symbol = cls.first(row, cls.SYMBOL_KEYS)
        series = cls.first(row, cls.SERIES_KEYS)
        open_ = cls.first(row, cls.OPEN_KEYS)
        high = cls.first(row, cls.HIGH_KEYS)
        low = cls.first(row, cls.LOW_KEYS)
        close = cls.first(row, cls.CLOSE_KEYS)
        volume = cls.first(row, cls.VOLUME_KEYS)
        if (
            symbol is None
            or series is None
            or open_ is None
            or high is None
            or low is None
            or close is None
            or volume is None
        ):
            return None
        try:
            open_f = float(open_)
            high_f = float(high)
            low_f = float(low)
            close_f = float(close)
            volume_i = int(float(volume))
        except ValueError:
            logger.warning("Skipping bhavcopy row with bad numerics on %s: %s", trade_date, symbol)
            return None
        isin = cls.first(row, cls.ISIN_KEYS)
        row_date = cls.parse_row_date(row) or trade_date
        return {
            "trade_date": row_date,
            "symbol": symbol.strip().upper(),
            "series": series.strip().upper(),
            "open": open_f,
            "high": high_f,
            "low": low_f,
            "close": close_f,
            "volume": volume_i,
            "isin": isin.strip() if isin else None,
        }

    @staticmethod
    def first(row: dict[str, str], keys: tuple[str, ...]) -> str | None:
        for key in keys:
            value = row.get(key)
            if value is not None and str(value).strip() != "":
                return str(value)
        return None

    @classmethod
    def parse_row_date(cls, row: dict[str, str]) -> date | None:
        raw = cls.first(row, cls.DATE_KEYS)
        if raw is None:
            return None
        text = raw.strip()
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            pass
        for fmt in ("%d-%b-%Y", "%d-%b-%y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None


class FoBhavcopyRow:
    """Normalize one F&O bhavcopy CSV row into an FoRow."""

    @classmethod
    def from_row(cls, row: dict[str, str], *, trade_date: date) -> FoRow | None:
        symbol = BhavcopyRow.first(row, ("TckrSymb", "SYMBOL"))
        instrument = BhavcopyRow.first(row, ("FinInstrmTp", "INSTRUMENT"))
        open_ = BhavcopyRow.first(row, ("OpnPric", "OPEN"))
        high = BhavcopyRow.first(row, ("HghPric", "HIGH"))
        low = BhavcopyRow.first(row, ("LwPric", "LOW"))
        close = BhavcopyRow.first(row, ("ClsPric", "CLOSE"))
        volume = BhavcopyRow.first(row, ("TtlTradgVol", "CONTRACTS", "Tottrdqty"))
        if (
            symbol is None
            or instrument is None
            or open_ is None
            or high is None
            or low is None
            or close is None
            or volume is None
        ):
            return None
        try:
            open_f = float(open_)
            high_f = float(high)
            low_f = float(low)
            close_f = float(close)
            volume_i = int(float(volume))
        except ValueError:
            return None
        strike_raw = BhavcopyRow.first(row, ("StrkPric", "STRIKE_PR"))
        oi_raw = BhavcopyRow.first(row, ("OpnIntrst", "OPEN_INT"))
        strike = float(strike_raw) if strike_raw not in (None, "") else None
        open_interest = int(float(oi_raw)) if oi_raw not in (None, "") else None
        expiry = cls._parse_date(BhavcopyRow.first(row, ("XpryDt", "EXPIRY_DT")))
        option_type = BhavcopyRow.first(row, ("OptnTp", "OPTION_TYP"))
        row_date = BhavcopyRow.parse_row_date(row) or trade_date
        return {
            "trade_date": row_date,
            "symbol": symbol.strip().upper(),
            "instrument_type": instrument.strip().upper(),
            "expiry": expiry,
            "strike": strike,
            "option_type": option_type.strip().upper() if option_type else None,
            "open": open_f,
            "high": high_f,
            "low": low_f,
            "close": close_f,
            "volume": volume_i,
            "open_interest": open_interest,
        }

    @staticmethod
    def _parse_date(raw: str | None) -> date | None:
        if raw is None or not raw.strip():
            return None
        text = raw.strip()
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            pass
        for fmt in ("%d-%b-%Y", "%d-%b-%y", "%d-%m-%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None


class IndexClosesRow:
    """Normalize one index-closes CSV row into an IndexRow."""

    @classmethod
    def from_row(cls, row: dict[str, str], *, trade_date: date) -> IndexRow | None:
        name = BhavcopyRow.first(row, ("Index Name", "IndexName"))
        open_ = BhavcopyRow.first(row, ("Open Index Value", "Open"))
        high = BhavcopyRow.first(row, ("High Index Value", "High"))
        low = BhavcopyRow.first(row, ("Low Index Value", "Low"))
        close = BhavcopyRow.first(row, ("Closing Index Value", "Close"))
        if name is None or open_ is None or high is None or low is None or close is None:
            return None
        if open_ in ("-", "") or high in ("-", "") or low in ("-", "") or close in ("-", ""):
            return None
        try:
            return {
                "trade_date": trade_date,
                "index_name": name.strip(),
                "open": float(open_),
                "high": float(high),
                "low": float(low),
                "close": float(close),
            }
        except ValueError:
            return None
