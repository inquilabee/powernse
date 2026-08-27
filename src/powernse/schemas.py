from datetime import date
from typing import TypedDict

import pandas as pd
from pdschema import Column, Schema


class OhlcRow(TypedDict):
    """One parsed bhavcopy row, matching ``OhlcSchema``'s columns."""

    trade_date: date
    symbol: str
    series: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    isin: str | None


class FoRow(TypedDict):
    """One parsed F&O bhavcopy row, matching ``FoSchema``'s columns."""

    trade_date: date
    symbol: str
    instrument_type: str
    expiry: date | None
    strike: float | None
    option_type: str | None
    open: float
    high: float
    low: float
    close: float
    volume: int
    open_interest: int | None


class IndexRow(TypedDict):
    """One parsed index-closes row, matching ``IndexSchema``'s columns."""

    trade_date: date
    index_name: str
    open: float
    high: float
    low: float
    close: float


class OhlcSchema(Schema):
    trade_date = Column(dtype=date, nullable=False)
    symbol = Column(dtype=str, nullable=False)
    series = Column(dtype=str, nullable=False)
    open = Column(dtype=float, nullable=False)
    high = Column(dtype=float, nullable=False)
    low = Column(dtype=float, nullable=False)
    close = Column(dtype=float, nullable=False)
    volume = Column(dtype=int, nullable=False)
    isin = Column(dtype=str, nullable=True)


class AdjustedOhlcSchema(Schema):
    trade_date = Column(dtype=date, nullable=False)
    symbol = Column(dtype=str, nullable=False)
    series = Column(dtype=str, nullable=False)
    open = Column(dtype=float, nullable=False)
    high = Column(dtype=float, nullable=False)
    low = Column(dtype=float, nullable=False)
    close = Column(dtype=float, nullable=False)
    volume = Column(dtype=int, nullable=False)
    factor = Column(dtype=float, nullable=False)
    isin = Column(dtype=str, nullable=True)


class FoSchema(Schema):
    trade_date = Column(dtype=date, nullable=False)
    symbol = Column(dtype=str, nullable=False)
    instrument_type = Column(dtype=str, nullable=False)
    expiry = Column(dtype=date, nullable=True)
    strike = Column(dtype=float, nullable=True)
    option_type = Column(dtype=str, nullable=True)
    open = Column(dtype=float, nullable=False)
    high = Column(dtype=float, nullable=False)
    low = Column(dtype=float, nullable=False)
    close = Column(dtype=float, nullable=False)
    volume = Column(dtype=int, nullable=False)
    open_interest = Column(dtype=int, nullable=True)


class IndexSchema(Schema):
    trade_date = Column(dtype=date, nullable=False)
    index_name = Column(dtype=str, nullable=False)
    open = Column(dtype=float, nullable=False)
    high = Column(dtype=float, nullable=False)
    low = Column(dtype=float, nullable=False)
    close = Column(dtype=float, nullable=False)


OHLC_SCHEMA = OhlcSchema()
ADJUSTED_OHLC_SCHEMA = AdjustedOhlcSchema()
FO_SCHEMA = FoSchema()
INDEX_SCHEMA = IndexSchema()


def empty_frame(schema: Schema) -> pd.DataFrame:
    """An empty, correctly-columned DataFrame for a "no rows found" result."""
    return pd.DataFrame(columns=list(schema.columns))
