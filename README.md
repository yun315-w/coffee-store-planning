# Coffee Store Planning

**Team name:** team9

A Streamlit dashboard for the manager of one coffee store to review sales demand, prepare drinks before busy hours, and review shift coverage.

## Step 1 — Dataset and decision-maker

### Dataset, source and scope

I use [Coffee Shop Sales Dataset on Kaggle](https://www.kaggle.com/datasets/srisyra02/coffee-shop-sales-dataset), uploaded by Srimathy Sivanessan. This is the input dataset linked from the [Coffee Shop Sales EDA 100% notebook](https://www.kaggle.com/code/lalit7881/coffee-shop-sales-eda-100/input), the entry point identified from our group exercise. The original [Maven Analytics description](https://mavenanalytics.io/data-playground/coffee-shop-sales) describes Maven Roasters as a fictitious coffee business with three New York City locations. I therefore treat these records as simulated business data, rather than verified sales from a real company.

The local `Coffee Shop Sales.csv` contains **149,116 rows and 11 columns**, covers **January 1–June 30, 2023**, and is **13.33 MB**, below the approximately 25 MB guideline. I keep the full CSV without sampling. The EDA and dashboard aggregate records for analysis, but the source file remains unchanged.

One row records a product sold at a store and time, including its quantity and unit price. Although the identifier is named `transaction_id`, the file has no customer or receipt identifier. I call row counts **sales records**, rather than customers or complete orders.

### One decision-maker

The intended user is **the manager of one store**, responsible for preparation and weekly shift planning. The store filter allows this demonstration to serve any of the three locations; the manager selects their own store and reviews that store's demand.

## Step 2 — Why this dashboard is useful

### Who uses it, and how often?

The manager checks it briefly before opening and reviews it more closely during weekly planning. The daily check identifies preparation priorities, while the weekly review checks whether the busiest hours or the level of demand are changing.

### What decision does it support?

**If the store manager sees sustained growth in freshly prepared drink demand at a particular hour, they will move preparation and ingredient checks ahead of that hour and review how existing staff are allocated around the peak.**

Drink sales indicate preparation workload, but they do not directly calculate staffing requirements. The dataset contains no staff hours or service times, so the dashboard supports a review of coverage rather than prescribing a headcount.

### What happens without it?

For this business scenario, I assume the manager would otherwise summarize sales exports manually or rely on experience. Repeating that work could take time and make it easier to overlook a shifting peak or confuse higher prices with higher sales activity. These are proposed operational risks; the dataset does not measure the manager's actual workflow, time savings or financial losses.

### Why a dashboard rather than an email, report or alert?

The manager repeatedly needs to answer the same questions and compare different periods. A dashboard lets them change the store and date range, then inspect the relevant hours immediately. A fixed weekly email cannot provide that filtering, and a one-off report would need to be rebuilt as new data arrives. An alert could flag a specific exception in a future system, but the manager would still need the trend and hourly context to decide what to do.

## Step 3 — EDA, display choices and page order

### EDA findings behind the design

`Preprocessing.ipynb` contains the executed Pandas and Matplotlib analysis of shape, types, missing values, distributions, duplicates and relationships across time, products and stores. Three findings informed my choices:

- Across all stores, June revenue is **103.83% higher than January revenue**. This makes a time trend useful for checking whether business activity is changing.
- **08:00–10:59 accounts for 36.19% of all-product sales records**. This motivates examining demand by hour; the dashboard then uses freshly prepared drink units to focus on preparation workload.
- February revenue is **6.77% below January**, but revenue per calendar day is **3.21% higher**. Month lengths can change the apparent story, so comparable periods and calendar-based denominators matter.

These are findings about this six-month snapshot. They do not establish annual seasonality or explain what caused demand to change.

### Exactly three headline metrics

The app displays the following metrics side by side using `st.columns` and `st.metric`:

| Metric | Definition | Why the manager needs it |
|---|---|---|
| Sales revenue | Sum of each row's quantity × actual unit price | Shows the overall value of recorded sales and whether it changed from the preceding period. |
| Freshly prepared drinks | Units sold in Coffee, Tea and Drinking Chocolate | Provides the closest available indicator of drink-preparation workload. |
| Sales records | Number of source rows | Helps distinguish a change in sales activity from a change in revenue alone; it is not a count of customers or complete orders. |

Revenue covers all product categories; drink units cover only the three named categories. I retain both because business revenue and preparation workload answer different questions. USD is a business-context assumption based on the NYC setting; the CSV does not specify currency.

### Exactly two supporting charts

1. **Daily revenue trend:** compares the selected period with the immediately preceding period of equal length. It shows whether a headline revenue change is spread across dates or concentrated in a few days. The previous period is aligned by day within the period, and the hover label gives its actual date.
2. **Weekday × hour drink-demand heatmap:** shows average freshly prepared drink units per observed date of each weekday and hour. It identifies preparation priorities that an overall revenue total cannot locate. Each denominator includes observed store-dates with zero drink sales at that hour, so the average is not inflated by counting only dates with purchases.

### Only two filters

- **Store:** keeps the decision focused on the manager's own location.
- **Date range:** supports the daily check and comparison of recent periods during weekly planning.

I exclude product and price sliders because the main question is when preparation should be ready, rather than which product has the highest price. The default period is **June 3–30, 2023**, compared with **May 6–June 2, 2023**. Both are 28-day windows containing four of each weekday. For other selections, the app flags uneven weekday counts and hides percentage comparisons when either period lacks full observed store-date coverage or the relevant previous value is zero.

### Two things I chose not to show

1. **A top-ten product ranking.** It could support a separate product-assortment decision, but it would not directly identify when the manager should prepare drinks. Adding it would distract from the time-based preparation question.
2. **A weekday sales-share pie chart.** Raw weekday totals depend on how many times each weekday occurs in the selected period. The heatmap already shows weekday patterns with a calendar-based denominator and adds the hourly detail needed for action.

### Page order and its reason

The page follows this layout:

```text
Title and purpose; selected store and dates
Three headline metrics
Daily revenue trend
Weekday × hour drink-demand heatmap and preparation focus
Collapsed chart data, metric definitions and data-quality notes
Snapshot dates and intended production refresh frequency
```

The manager first sees the scale of activity, then whether it is changing, and finally which time slots deserve attention. Supporting tables stay collapsed so they remain available without crowding the initial view. The sidebar holds the two filters.

### Misleading data and how I handle it

- **Text inconsistencies:** cleaning trims **1,952 text values** in memory while preserving all source rows.
- **Possible duplicates:** **398 additional rows** share the same business fields but have different IDs. I retain and disclose them because identical purchases can occur and the file does not prove an error.
- **Different prices for the same product:** **15 products** have multiple observed prices. Revenue uses the actual price in each row, without assuming a promotion or replacing it with a fixed product price.
- **Large purchases:** the maximum row value is **$360**. Such records are retained because a large quantity at a high unit price is not sufficient evidence of a mistake.
- **Missing coverage versus zero demand:** dates without store records remain unavailable. Grey heatmap cells represent unavailable weekday/hour combinations, rather than confirmed zero demand or closure. Observed hours are not independently verified opening hours.
- **Metric limits:** the app explains that sales records are not customers or complete orders, and revenue is not profit. It makes no claims about retention, inventory shortages or staffing efficiency because the required data is absent.

## Step 4 — Refresh, review and action

### How often should the data refresh?

In a production version, I would load the completed day's point-of-sale records **nightly after closing**, ready for the next opening. The manager can act on preparation before a shift and on coverage during weekly planning, so refreshing every minute would add complexity without changing those decisions. This demonstration uses a frozen CSV and does not implement that production feed.

### How often should the manager review it?

The manager should make a **brief check before opening** and a **fuller review during weekly planning**. Refresh frequency determines when new data becomes available; review frequency follows when the manager can act on it.

### What should be tracked, and what triggers action?

I would track **average freshly prepared drink units in each weekday/hour slot**. At each weekly review, compare the latest complete four weeks with the preceding four weeks for the same store and slot. A **rise above 20% at two consecutive weekly reviews** would trigger a review of preparation timing and staff allocation around that slot, provided the earlier average is positive and both periods have coverage. A previously zero-demand slot would require a separate manual check rather than a percentage calculation.

The 20% threshold and two-review rule are proposed starting points for discussion with the manager, not values validated by this dataset. They aim to focus attention on sustained changes and would need adjustment using service outcomes and operating experience. The current app supports manual comparison by changing the date range; it does not calculate this threshold or issue automatic alerts.

### What does stale data cost?

A day-old view could miss a recent change and leave preparation poorly matched to the next shift. A week-old view could carry an outdated demand pattern into the next week's preparation and shift plan. That could mean unnecessary early preparation or insufficient preparation before a busy hour, but the dataset cannot quantify waste, queues or lost sales. The app therefore states the snapshot period and intended nightly refresh frequency instead of presenting historical figures as live conditions.

## Run the app

Run from the app repository folder:

```bash
uv sync --locked
uv run streamlit run app.py
```

The app loads `Coffee Shop Sales.csv` from the same folder as `app.py`. To use the existing EDA notebook locally, install its optional dependencies with `uv sync --locked --group notebook`. For the course deployment, select **Python 3.14** in Streamlit Community Cloud's Advanced settings.

## Repository files

- `app.py`: dashboard interface.
- `coffee_data.py`: cleaning and calendar-aware aggregation.
- `Coffee Shop Sales.csv`: original data snapshot.
- `Preprocessing.ipynb`: executed EDA.
- `pyproject.toml`, `uv.lock` and `.python-version`: environment configuration.
- `.streamlit/config.toml`: app theme and server configuration.
- `tests/`: existing checks for data handling and the app.
