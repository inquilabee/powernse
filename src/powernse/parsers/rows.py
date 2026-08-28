"""CSV row normalizers for staged NSE archives.

One :class:`RowParser` subclass per raw file shape. The base runs the shared
pipeline -- pick required fields by candidate key, coerce the numeric ones,
bail to ``None`` on anything missing or unparseable -- and each subclass only
declares its field map and assembles the typed row in ``_build``.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import date, datetime
from typing import ClassVar

from powernse.schemas import DealRow, DeliveryRow, FoRow, IndexRow, OhlcRow

logger = logging.getLogger(__name__)

RawRow = Mapping[str, str]
FieldMap = Mapping[str, tuple[str, ...]]

type SchemaRow = OhlcRow | FoRow | IndexRow | DeliveryRow | DealRow


class RowParser[RowT: SchemaRow](ABC):
    """Turn one raw CSV row into a typed schema row, or ``None`` when it can't."""

    #: logical field name -> candidate CSV column names (first non-empty wins)
    REQUIRED: ClassVar[FieldMap] = {}
    #: subset of REQUIRED whose values must parse as ``float``
    NUMERIC: ClassVar[tuple[str, ...]] = ()
    #: extra sentinel values that count as "missing" for a NUMERIC field
    NUMERIC_BLANKS: ClassVar[frozenset[str]] = frozenset()
    #: characters stripped from a NUMERIC value before ``float()`` (e.g. thousands commas)
    NUMERIC_STRIP: ClassVar[str] = ""
    #: strptime formats tried (after ISO) for the row's trade-date
    DATE_FORMATS: ClassVar[tuple[str, ...]] = ("%d-%b-%Y", "%d-%b-%y")

    def from_row(self, row: RawRow, *, trade_date: date) -> RowT | None:
        picked = self._pick(row, self.REQUIRED)
        if picked is None:
            return None
        if any(picked[name] in self.NUMERIC_BLANKS for name in self.NUMERIC):
            return None
        numbers = self._floats(picked, self.NUMERIC)
        if numbers is None:
            self._on_bad_numerics(trade_date, picked)
            return None
        return self._build(row, picked, numbers, trade_date)

    @abstractmethod
    def _build(self, row: RawRow, picked: dict[str, str], numbers: dict[str, float], trade_date: date) -> RowT: ...

    def _on_bad_numerics(self, trade_date: date, picked: dict[str, str]) -> None:  # noqa: B027
        """Optional hook: a required numeric field wouldn't parse. Default: drop the row silently."""
        return

    # -- shared helpers -------------------------------------------------------

    @staticmethod
    def first(row: RawRow, keys: tuple[str, ...]) -> str | None:
        for key in keys:
            value = row.get(key)
            if value is not None and (text := str(value).strip()):
                return text
        return None

    def _pick(self, row: RawRow, fields: FieldMap) -> dict[str, str] | None:
        picked: dict[str, str] = {}
        for name, keys in fields.items():
            value = self.first(row, keys)
            if value is None:
                return None
            picked[name] = value
        return picked

    def _floats(self, picked: dict[str, str], names: tuple[str, ...]) -> dict[str, float] | None:
        strip = self.NUMERIC_STRIP
        try:
            return {
                name: float(picked[name].translate({ord(c): None for c in strip}) if strip else picked[name])
                for name in names
            }
        except ValueError:
            return None

    def optional_float(self, row: RawRow, keys: tuple[str, ...]) -> float | None:
        raw = self.first(row, keys)
        return None if raw is None or raw in self.NUMERIC_BLANKS else float(raw)

    def parse_date(self, raw: str | None, *, formats: tuple[str, ...] | None = None) -> date | None:
        if raw is None or not (text := raw.strip()):
            return None
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            pass
        for fmt in formats or self.DATE_FORMATS:
            try:
                return datetime.strptime(text, fmt).date()  # noqa: DTZ007 -- naive date is intended
            except ValueError:
                continue
        return None


class BhavcopyRowParser(RowParser[OhlcRow]):
    """Legacy or UDIFF CM bhavcopy row -> :class:`OhlcRow`."""

    REQUIRED: ClassVar[FieldMap] = {
        "symbol": ("SYMBOL", "TckrSymb"),
        "series": ("SERIES", "SctySrs"),
        "open": ("OPEN", "OpnPric"),
        "high": ("HIGH", "HghPric"),
        "low": ("LOW", "LwPric"),
        "close": ("CLOSE", "ClsPric"),
        "volume": ("TOTTRDQTY", "TtlTradgVol"),
    }
    NUMERIC = ("open", "high", "low", "close", "volume")
    ISIN_KEYS = ("ISIN",)
    DATE_KEYS = ("TradDt", "TIMESTAMP")

    def _on_bad_numerics(self, trade_date: date, picked: dict[str, str]) -> None:
        logger.warning("Skipping bhavcopy row with bad numerics on %s: %s", trade_date, picked["symbol"])

    def _build(self, row: RawRow, picked: dict[str, str], numbers: dict[str, float], trade_date: date) -> OhlcRow:
        isin = self.first(row, self.ISIN_KEYS)
        return {
            "trade_date": self.parse_date(self.first(row, self.DATE_KEYS)) or trade_date,
            "symbol": picked["symbol"].upper(),
            "series": picked["series"].upper(),
            "open": numbers["open"],
            "high": numbers["high"],
            "low": numbers["low"],
            "close": numbers["close"],
            "volume": int(numbers["volume"]),
            "isin": isin or None,
        }


class FoBhavcopyRowParser(RowParser[FoRow]):
    """F&O bhavcopy row -> :class:`FoRow`."""

    REQUIRED: ClassVar[FieldMap] = {
        "symbol": ("TckrSymb", "SYMBOL"),
        "instrument_type": ("FinInstrmTp", "INSTRUMENT"),
        "open": ("OpnPric", "OPEN"),
        "high": ("HghPric", "HIGH"),
        "low": ("LwPric", "LOW"),
        "close": ("ClsPric", "CLOSE"),
        "volume": ("TtlTradgVol", "CONTRACTS", "Tottrdqty"),
    }
    NUMERIC = ("open", "high", "low", "close", "volume")
    DATE_KEYS = ("TradDt", "TIMESTAMP")
    #: expiry accepts a numeric-month form the trade-date field never uses
    EXPIRY_FORMATS = ("%d-%b-%Y", "%d-%b-%y", "%d-%m-%Y")
    STRIKE_KEYS = ("StrkPric", "STRIKE_PR")
    OI_KEYS = ("OpnIntrst", "OPEN_INT")
    EXPIRY_KEYS = ("XpryDt", "EXPIRY_DT")
    OPTION_TYPE_KEYS = ("OptnTp", "OPTION_TYP")

    def _build(self, row: RawRow, picked: dict[str, str], numbers: dict[str, float], trade_date: date) -> FoRow:
        strike = self.first(row, self.STRIKE_KEYS)
        open_interest = self.first(row, self.OI_KEYS)
        option_type = self.first(row, self.OPTION_TYPE_KEYS)
        return {
            "trade_date": self.parse_date(self.first(row, self.DATE_KEYS)) or trade_date,
            "symbol": picked["symbol"].upper(),
            "instrument_type": picked["instrument_type"].upper(),
            "expiry": self.parse_date(self.first(row, self.EXPIRY_KEYS), formats=self.EXPIRY_FORMATS),
            "strike": float(strike) if strike is not None else None,
            "option_type": option_type.upper() if option_type else None,
            "open": numbers["open"],
            "high": numbers["high"],
            "low": numbers["low"],
            "close": numbers["close"],
            "volume": int(numbers["volume"]),
            "open_interest": int(float(open_interest)) if open_interest is not None else None,
        }


class IndexClosesRowParser(RowParser[IndexRow]):
    """All-index closes row -> :class:`IndexRow`. Dashes count as missing."""

    REQUIRED: ClassVar[FieldMap] = {
        "index_name": ("Index Name", "IndexName"),
        "open": ("Open Index Value", "Open"),
        "high": ("High Index Value", "High"),
        "low": ("Low Index Value", "Low"),
        "close": ("Closing Index Value", "Close"),
    }
    NUMERIC = ("open", "high", "low", "close")
    NUMERIC_BLANKS = frozenset({"-"})

    def _build(self, row: RawRow, picked: dict[str, str], numbers: dict[str, float], trade_date: date) -> IndexRow:
        del row
        return {
            "trade_date": trade_date,
            "index_name": picked["index_name"],
            "open": numbers["open"],
            "high": numbers["high"],
            "low": numbers["low"],
            "close": numbers["close"],
        }


class DeliveryRowParser(RowParser[DeliveryRow]):
    """``sec_bhavdata_full`` row -> :class:`DeliveryRow`. DELIV_* is ``-`` for non-delivery series."""

    REQUIRED: ClassVar[FieldMap] = {
        "symbol": ("SYMBOL",),
        "series": ("SERIES",),
        "prev_close": ("PREV_CLOSE",),
        "close": ("CLOSE_PRICE",),
        "avg_price": ("AVG_PRICE",),
        "volume": ("TTL_TRD_QNTY",),
        "turnover_lacs": ("TURNOVER_LACS",),
        "trades": ("NO_OF_TRADES",),
    }
    NUMERIC = ("prev_close", "close", "avg_price", "volume", "turnover_lacs", "trades")
    NUMERIC_STRIP = ","
    NUMERIC_BLANKS = frozenset({"-"})
    DATE_KEYS = ("DATE1",)
    DELIV_QTY_KEYS = ("DELIV_QTY",)
    DELIV_PER_KEYS = ("DELIV_PER",)

    def _build(self, row: RawRow, picked: dict[str, str], numbers: dict[str, float], trade_date: date) -> DeliveryRow:
        qty = self.optional_float(row, self.DELIV_QTY_KEYS)
        pct = self.optional_float(row, self.DELIV_PER_KEYS)
        return {
            "trade_date": self.parse_date(self.first(row, self.DATE_KEYS)) or trade_date,
            "symbol": picked["symbol"].upper(),
            "series": picked["series"].upper(),
            "prev_close": numbers["prev_close"],
            "close": numbers["close"],
            "avg_price": numbers["avg_price"],
            "volume": int(numbers["volume"]),
            "turnover_lacs": numbers["turnover_lacs"],
            "trades": int(numbers["trades"]),
            "delivery_qty": int(qty) if qty is not None else None,
            "delivery_pct": pct,
        }


class DealRowParser(RowParser[DealRow]):
    """Bulk- or block-deal row -> :class:`DealRow` (block has no ``Remarks``)."""

    REQUIRED: ClassVar[FieldMap] = {
        "trade_date": ("Date",),
        "symbol": ("Symbol",),
        "security_name": ("Security Name",),
        "client_name": ("Client Name",),
        "side": ("Buy/Sell",),
        "quantity": ("Quantity Traded",),
        "price": ("Trade Price / Wght. Avg. Price",),
    }
    NUMERIC = ("quantity", "price")
    NUMERIC_STRIP = ","

    def _build(self, row: RawRow, picked: dict[str, str], numbers: dict[str, float], trade_date: date) -> DealRow:
        del row
        return {
            "trade_date": self.parse_date(picked["trade_date"]) or trade_date,
            "symbol": picked["symbol"].upper(),
            "security_name": picked["security_name"],
            "client_name": picked["client_name"],
            "side": picked["side"].strip().upper(),
            "quantity": int(numbers["quantity"]),
            "price": numbers["price"],
        }


BHAVCOPY_ROWS = BhavcopyRowParser()
FO_BHAVCOPY_ROWS = FoBhavcopyRowParser()
INDEX_CLOSES_ROWS = IndexClosesRowParser()
DELIVERY_ROWS = DeliveryRowParser()
DEAL_ROWS = DealRowParser()
