"""Run with: uv run streamlit run app.py"""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from coffee_data import (
    WEEKDAYS, daily_series, has_full_coverage, hourly_demand, load_sales,
    make_period, percent_change, select_period, totals,
)

TEAM_NAME = "team9"
DATA_PATH = Path(__file__).resolve().parent / "Coffee Shop Sales.csv"
TEAL = "#247266"

st.set_page_config(page_title="Coffee Store Planning", page_icon="☕", layout="wide")
st.markdown("""
<style>
 .stMainBlockContainer { max-width: 1120px; padding-top: 2rem; padding-bottom: 2rem; }
 h1 { font-size: 2rem !important; line-height: 1.2 !important; }
 h2, h3 { font-size: 1.25rem !important; }
 [data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; font-size: 1.85rem; }
 button:focus-visible, input:focus-visible { outline: 2px solid #247266; outline-offset: 3px; }
 @media (min-width: 641px) and (max-width: 1100px) {
   [data-testid="stMetricValue"] { font-size: 1rem !important; }
   [data-testid="stMetricLabel"] p {
     white-space: normal !important; overflow: visible !important;
     font-size: 0.75rem !important; line-height: 1.3 !important;
   }
   [data-testid="stMetricLabel"] { min-height: 2.6em; }
 }
 @media (max-width: 640px) {
   .stMainBlockContainer { padding-top: 1.2rem; padding-left: 1rem; padding-right: 1rem; }
   h1 { font-size: 1.6rem !important; }
   [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) { flex-direction: column; }
   [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > div { width: 100% !important; flex: 1 1 100% !important; }
 }
 @media (prefers-reduced-motion: reduce) {
   *, *::before, *::after { animation: none !important; transition: none !important; }
 }
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def cached_sales(path: str, modified_ns: int):
    # Include file modification time in the cache key when the source is replaced.
    return load_sales(path)


try:
    with st.spinner("Loading store sales…"):
        sales = cached_sales(str(DATA_PATH), DATA_PATH.stat().st_mtime_ns)
except (OSError, ValueError, pd.errors.ParserError) as exc:
    st.title("Coffee Store Planning")
    st.error("Sales data could not be loaded. Restore the original CSV and review its format.")
    with st.expander("Data issue details"):
        st.code(str(exc))
    st.stop()

df = sales.frame
minimum, maximum = df.date.min(), df.date.max()
default_start = max(minimum, maximum - pd.Timedelta(days=27))
stores = sorted(df.store_location.unique())

with st.sidebar:
    st.header("Plan your store")
    selected_store = st.selectbox("Store", stores, index=stores.index("Lower Manhattan") if "Lower Manhattan" in stores else 0)
    selected_dates = st.date_input("Date range", value=(default_start.date(), maximum.date()),
                                   min_value=minimum.date(), max_value=maximum.date(), format="YYYY-MM-DD")
    st.caption("Default: the latest complete 4 weeks in this snapshot. Comparisons use the immediately preceding period of equal length.")
    st.divider()
    st.caption("For a store manager reviewing preparation before the next shift and planning the next week.")

st.title(f"{TEAM_NAME} · Store Planning")
st.caption("For store managers deciding when to prepare more drinks and review shift coverage.")

if len(selected_dates) != 2:
    st.info("Choose an end date to complete your date range.")
    st.stop()
period = make_period(*selected_dates)
store = df.loc[df.store_location.eq(selected_store)]
current = select_period(store, period.start, period.end)
previous = select_period(store, period.previous_start, period.previous_end)
if current.empty:
    st.info("No sales records for this selection. Choose another store or date range.")
    st.stop()

current_complete = has_full_coverage(store, period.start, period.end)
previous_complete = has_full_coverage(store, period.previous_start, period.previous_end)
can_compare = current_complete and previous_complete
st.markdown(f"**{selected_store}** · {period.start:%d %b %Y} – {period.end:%d %b %Y} · {period.days} days")
if can_compare:
    st.caption(f"Changes versus {period.previous_start:%d %b} – {period.previous_end:%d %b %Y}, the preceding {period.days} days.")
else:
    st.caption("Comparison unavailable: a complete preceding period is not present for this store. Changes are hidden.")
if not current_complete:
    missing_days = period.days - current.date.nunique()
    st.warning(f"{missing_days} selected date(s) have no store records. Totals cover recorded sales only; unobserved days are not treated as zero sales.")
if period.days % 7:
    st.caption("This range contains uneven weekday counts. Heatmap values are normalized by observed dates; KPI comparisons may reflect a different weekday mix.")

current_totals, previous_totals = totals(current), totals(previous)
metric_specs = [
    ("Sales revenue", "revenue_cents", f"${current_totals['revenue_cents'] / 100:,.2f}", "Recorded quantity × actual unit price. USD is the currency assumption for this NYC dataset; this is not profit."),
    ("Freshly prepared drinks", "drinks", f"{current_totals['drinks']:,}", "Units in Coffee, Tea and Drinking Chocolate. Excludes beans, merchandise, syrups and bakery items. A workload proxy, not required staff hours."),
    ("Sales records", "records", f"{current_totals['records']:,}", "Number of source rows. The dataset has no receipt or customer IDs; this is not customer count or complete order count."),
]
for column, (label, key, value, help_text) in zip(st.columns(3), metric_specs):
    change = percent_change(current_totals[key], previous_totals[key]) if can_compare else None
    column.metric(label, value, delta=f"{change:+.1f}%" if change is not None else None,
                  delta_color="off", help=help_text, border=True)


def chart_style(chart):
    # Let Streamlit supply readable axis and legend colors for the active theme.
    return chart.configure_view(stroke=None).configure_axis(
        labelFontSize=11, titleFontSize=11, domain=False, tickSize=3,
    ).configure_legend(title=None, orient="top")


st.subheader("Is sales demand changing?")
trend_data = daily_series(store, period, can_compare)
trend = alt.Chart(trend_data).mark_line(point=alt.OverlayMarkDef(size=20), strokeWidth=2,
                                       invalid="break-paths-show-domains").encode(
    x=alt.X("plot_date:T", title=None, axis=alt.Axis(format="%d %b", tickCount=5, labelAngle=0)),
    y=alt.Y("revenue_usd:Q", title="Daily sales (USD)", scale=alt.Scale(zero=True), axis=alt.Axis(format="$,.0f")),
    color=alt.Color("period:N", scale=alt.Scale(domain=["Selected period", "Previous period"], range=[TEAL, "#90978E"])),
    strokeDash=alt.StrokeDash("period:N", scale=alt.Scale(domain=["Selected period", "Previous period"], range=[[1, 0], [5, 4]]), legend=alt.Legend(title=None)),
    tooltip=[alt.Tooltip("period:N", title="Period"), alt.Tooltip("source_date:T", title="Actual date", format="%d %b %Y"),
             alt.Tooltip("revenue_usd:Q", title="Sales (USD)", format="$,.2f")],
).properties(height=235, description="Daily revenue for the selected store, with the preceding period aligned by day when fully available.")
st.altair_chart(chart_style(trend), width="stretch", theme="streamlit")
st.caption("The dashed comparison is aligned by day within the period; its actual date appears on hover. Equal 28-day windows keep weekday counts comparable.")

st.subheader("When should preparation be ready?")
heatmap_data = hourly_demand(store, current)
heatmap = alt.Chart(heatmap_data).mark_rect(cornerRadius=2, stroke="#FCFBF8", strokeWidth=2).encode(
    x=alt.X("hour:O", title="Hour of day", sort=list(range(6, 21)), axis=alt.Axis(labelAngle=0)),
    y=alt.Y("weekday:N", title=None, sort=WEEKDAYS),
    color=alt.condition("isValid(datum.avg_drinks)",
        alt.Color("avg_drinks:Q", title="Drinks / day / hour", scale=alt.Scale(scheme="tealblues", domainMin=0),
                  legend=alt.Legend(orient="bottom", direction="horizontal", gradientLength=160)), alt.value("#E3E5E0")),
    tooltip=[alt.Tooltip("weekday:N", title="Weekday"), alt.Tooltip("hour_label:N", title="Hour"),
             alt.Tooltip("avg_drinks:Q", title="Average drinks", format=".1f"),
             alt.Tooltip("observed_days:Q", title="Observed dates", format="d"),
             alt.Tooltip("availability:N", title="Coverage")],
).properties(height=245, description="Weekday-by-hour heatmap of average freshly prepared drink units. Grey means unavailable, not zero demand.")
st.altair_chart(chart_style(heatmap), width="stretch", theme="streamlit")
st.caption("Each cell divides drink units by observed dates of that weekday, including dates with zero drinks at that hour. Grey = no matching dates or outside the store’s observed hour range. Recorded hours are not confirmed opening hours.")

drinks_by_hour = current.loc[current.is_drink].groupby("hour").transaction_qty.sum()
if not drinks_by_hour.empty:
    peak_hour = int(drinks_by_hour.idxmax())
    peak_share = drinks_by_hour.max() / drinks_by_hour.sum()
    st.markdown(f"**Preparation focus:** {peak_hour:02}:00–{peak_hour:02}:59 has the largest recorded drink volume ({peak_share:.1%} of selected drinks). Review preparation before this hour; sales alone cannot determine staffing levels.")
else:
    st.info("No freshly prepared drinks were recorded in this selection.")

with st.expander("Chart data and metric definitions"):
    st.markdown("**Sales records are not customers or receipt-level orders.** Fresh drinks include Coffee, Tea and Drinking Chocolate. Revenue includes all recorded product categories; amounts are computed in integer cents.")
    st.markdown("**Daily sales**")
    st.dataframe(trend_data[["source_date", "period", "revenue_usd"]].rename(columns={"source_date": "Actual date", "period": "Period", "revenue_usd": "Sales (USD)"}), hide_index=True, width="stretch")
    st.markdown("**Hourly drink demand**")
    st.dataframe(heatmap_data[["weekday", "hour_label", "avg_drinks", "observed_days", "availability"]].rename(columns={"weekday": "Weekday", "hour_label": "Hour", "avg_drinks": "Avg. drinks", "observed_days": "Observed dates", "availability": "Coverage"}), hide_index=True, width="stretch")

with st.expander("Data quality and limits"):
    st.markdown(f"Source contains **{len(df):,} rows**. Cleaning trimmed **{sales.whitespace_fixed:,}** text values and preserved all rows. **{sales.possible_duplicates:,}** additional rows share business fields but have different IDs; they remain pending source review. **{sales.variable_price_products}** products have multiple observed prices; each row retains its actual price.")
    st.markdown("High-value coffee-bean purchases are retained. Dates without store records are unavailable, not confirmed closures. There are no customer IDs, costs, inventory, staff hours or verified opening times. No customer retention, profit, stockout or staffing-efficiency claims are made.")
    st.markdown("Maven Roasters is a fictitious NYC coffee business. USD is assumed from the business context; the CSV has no currency or time-zone field. See README for provenance and decision rationale.")

st.divider()
st.caption(f"Data: {minimum:%d %b %Y} – {maximum:%d %b %Y} · Kaggle snapshot of a fictitious business · Intended production refresh: nightly after close; review: before opening and weekly planning.")
