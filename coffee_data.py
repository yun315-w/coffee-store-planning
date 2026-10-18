"""Conservative cleaning and calendar-aware aggregates for the dashboard."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = [
    "transaction_id", "transaction_date", "transaction_time", "transaction_qty",
    "store_id", "store_location", "product_id", "unit_price", "product_category",
    "product_type", "product_detail",
]
TEXT_COLUMNS = ["store_location", "product_category", "product_type", "product_detail"]
DRINK_CATEGORIES = ["Coffee", "Tea", "Drinking Chocolate"]
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass(frozen=True)
class SalesData:
    frame: pd.DataFrame
    whitespace_fixed: int
    possible_duplicates: int
    variable_price_products: int


@dataclass(frozen=True)
class Period:
    start: pd.Timestamp
    end: pd.Timestamp
    previous_start: pd.Timestamp
    previous_end: pd.Timestamp
    days: int


def load_sales(path: str | Path) -> SalesData:
    """Keep every valid source row; refuse ambiguous or invalid core data."""
    raw = pd.read_csv(path, encoding="utf-8-sig")
    missing = sorted(set(REQUIRED_COLUMNS) - set(raw.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    df = raw[REQUIRED_COLUMNS].copy()
    if df.empty:
        raise ValueError("Source data contains no sales records.")
    if df.isna().any().any():
        raise ValueError("Source data contains missing values. Review them before publishing.")
    possible_duplicates = int(df.duplicated(df.columns.drop("transaction_id").tolist()).sum())
    whitespace_fixed = 0
    for column in TEXT_COLUMNS:
        cleaned = df[column].astype("string").str.strip()
        whitespace_fixed += int(df[column].ne(cleaned).sum())
        if cleaned.eq("").any():
            raise ValueError(f"Blank labels in {column}.")
        df[column] = cleaned
    for column in ["transaction_id", "transaction_qty", "store_id", "product_id"]:
        values = pd.to_numeric(df[column], errors="coerce")
        if values.isna().any() or values.mod(1).ne(0).any() or values.le(0).any():
            raise ValueError(f"{column} must contain positive whole numbers.")
        df[column] = values.astype("int64")
    if df.transaction_id.duplicated().any():
        raise ValueError("Duplicate transaction IDs require review; no records were removed.")
    prices = pd.to_numeric(df.unit_price, errors="coerce")
    if prices.isna().any() or prices.le(0).any() or prices.isin([float('inf'), float('-inf')]).any():
        raise ValueError("Unit prices must be positive numbers.")
    if prices.mul(100).sub(prices.mul(100).round()).abs().gt(1e-6).any():
        raise ValueError("Unit prices with more than two decimal places require review.")
    df["unit_price"] = prices
    df["date"] = pd.to_datetime(df.transaction_date, format="%m/%d/%y", errors="coerce")
    parsed_time = pd.to_datetime(df.transaction_time, format="%H:%M:%S", errors="coerce")
    if df.date.isna().any() or parsed_time.isna().any():
        raise ValueError("Invalid dates or times. Expected MM/DD/YY and HH:MM:SS.")
    for key, label in [("store_id", "store_location"), ("store_location", "store_id"),
                       ("product_id", "product_detail"), ("product_id", "product_type"),
                       ("product_id", "product_category")]:
        if df.groupby(key)[label].nunique().gt(1).any():
            raise ValueError(f"Inconsistent mapping between {key} and {label}.")
    df["hour"] = parsed_time.dt.hour
    df["weekday_num"] = df.date.dt.dayofweek
    df["unit_price_cents"] = prices.mul(100).round().astype("int64")
    df["revenue_cents"] = df.transaction_qty * df.unit_price_cents
    df["is_drink"] = df.product_category.isin(DRINK_CATEGORIES)
    variable_prices = int(df.groupby("product_id").unit_price_cents.nunique().gt(1).sum())
    return SalesData(df, whitespace_fixed, possible_duplicates, variable_prices)


def make_period(start: date | pd.Timestamp, end: date | pd.Timestamp) -> Period:
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    if start > end:
        raise ValueError("Start date must be on or before end date.")
    days = (end - start).days + 1
    previous_end = start - pd.Timedelta(days=1)
    return Period(start, end, previous_end - pd.Timedelta(days=days - 1), previous_end, days)


def select_period(store: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    return store.loc[store.date.between(start, end)].copy()


def has_full_coverage(store: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> bool:
    expected = pd.date_range(start, end)
    observed = pd.DatetimeIndex(store.loc[store.date.between(start, end), "date"].unique())
    return len(expected.difference(observed)) == 0


def totals(rows: pd.DataFrame) -> dict[str, int]:
    return {"revenue_cents": int(rows.revenue_cents.sum()),
            "drinks": int(rows.loc[rows.is_drink, "transaction_qty"].sum()),
            "records": len(rows)}


def percent_change(current: int | float, previous: int | float) -> float | None:
    return None if previous <= 0 else (current / previous - 1) * 100


def daily_series(store: pd.DataFrame, period: Period, include_previous: bool) -> pd.DataFrame:
    """Missing store-days remain unavailable, never silently filled with sales zero."""
    blocks = []
    for start, end, label in [(period.start, period.end, "Selected period"),
                              (period.previous_start, period.previous_end, "Previous period")]:
        if label == "Previous period" and not include_previous:
            continue
        rows = select_period(store, start, end)
        daily = rows.groupby("date").revenue_cents.sum().reindex(pd.date_range(start, end))
        block = pd.DataFrame({"source_date": daily.index, "revenue_usd": daily.values / 100})
        block["plot_date"] = pd.date_range(period.start, period.end)
        block["period"] = label
        blocks.append(block)
    return pd.concat(blocks, ignore_index=True)


def hourly_demand(store: pd.DataFrame, selected: pd.DataFrame) -> pd.DataFrame:
    """Use observed calendar dates as the denominator, including zero-drink dates."""
    observed_dates = selected[["date", "weekday_num"]].drop_duplicates()
    denominators = observed_dates.groupby("weekday_num").size().reindex(range(7), fill_value=0)
    drinks = selected.loc[selected.is_drink]
    hours = range(6, 21)
    grid = pd.MultiIndex.from_product([range(7), hours], names=["weekday_num", "hour"])
    units = drinks.groupby(["weekday_num", "hour"]).transaction_qty.sum().reindex(grid, fill_value=0)
    heatmap = units.rename("drink_units").reset_index()
    heatmap["observed_days"] = heatmap.weekday_num.map(denominators)
    heatmap["avg_drinks"] = heatmap.drink_units.div(heatmap.observed_days.replace(0, float("nan")))
    # The source has no opening-hours schedule: do not invent demand outside observed hours.
    min_hour, max_hour = int(store.hour.min()), int(store.hour.max())
    heatmap.loc[~heatmap.hour.between(min_hour, max_hour), "avg_drinks"] = float("nan")
    heatmap["weekday"] = heatmap.weekday_num.map(dict(enumerate(WEEKDAYS)))
    heatmap["hour_label"] = heatmap.hour.map(lambda hour: f"{hour:02}:00")
    heatmap["availability"] = heatmap.avg_drinks.map(lambda x: "Unavailable" if pd.isna(x) else "Observed")
    return heatmap
