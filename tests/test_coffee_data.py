from pathlib import Path
import tempfile
import unittest

import pandas as pd

from coffee_data import (
    has_full_coverage, hourly_demand, load_sales, make_period,
    percent_change, select_period, totals,
)

ROOT = Path(__file__).resolve().parents[1]


class FullDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sales = load_sales(ROOT / "Coffee Shop Sales.csv")
        cls.df = cls.sales.frame

    def test_source_reconciles_to_known_totals(self):
        self.assertEqual(len(self.df), 149116)
        self.assertEqual(int(self.df.transaction_qty.sum()), 214470)
        self.assertEqual(totals(self.df)["revenue_cents"], 69881233)
        self.assertEqual(self.sales.whitespace_fixed, 1952)
        self.assertEqual(self.sales.possible_duplicates, 398)
        self.assertEqual(self.sales.variable_price_products, 15)

    def test_default_window_matches_weekdays_and_has_comparison(self):
        period = make_period("2023-06-03", "2023-06-30")
        self.assertEqual(period.days, 28)
        self.assertEqual(period.previous_start, pd.Timestamp("2023-05-06"))
        self.assertEqual(period.previous_end, pd.Timestamp("2023-06-02"))
        store = self.df.loc[self.df.store_location.eq("Lower Manhattan")]
        self.assertTrue(has_full_coverage(store, period.start, period.end))
        self.assertTrue(has_full_coverage(store, period.previous_start, period.previous_end))
        self.assertFalse(has_full_coverage(store, pd.Timestamp("2022-12-31"), pd.Timestamp("2023-01-01")))

    def test_missing_store_day_is_unavailable_not_sales_zero(self):
        from coffee_data import daily_series
        store = self.df.loc[self.df.store_location.eq("Lower Manhattan")]
        store = store.loc[store.date.ne(pd.Timestamp("2023-06-15"))]
        period = make_period("2023-06-03", "2023-06-30")
        self.assertFalse(has_full_coverage(store, period.start, period.end))
        daily = daily_series(store, period, False)
        self.assertTrue(pd.isna(daily.loc[daily.source_date.eq(pd.Timestamp("2023-06-15")), "revenue_usd"].iloc[0]))

    def test_unobserved_hours_and_absent_weekdays_remain_unavailable(self):
        store = self.df.loc[self.df.store_location.eq("Astoria")]
        selected = select_period(store, pd.Timestamp("2023-06-30"), pd.Timestamp("2023-06-30"))
        heatmap = hourly_demand(store, selected)
        self.assertTrue(heatmap.loc[heatmap.weekday_num.ne(4), "avg_drinks"].isna().all())
        self.assertTrue(heatmap.loc[heatmap.hour.eq(6), "avg_drinks"].isna().all())
        self.assertTrue(heatmap.loc[heatmap.hour.eq(20), "avg_drinks"].isna().all())

    def test_demand_denominator_includes_observed_dates_without_drinks(self):
        # Two observed Mondays. Only one has drinks; the other has a bakery record.
        rows = pd.DataFrame({
            "date": pd.to_datetime(["2023-06-05", "2023-06-12"]),
            "weekday_num": [0, 0], "hour": [10, 10],
            "is_drink": [True, False], "transaction_qty": [8, 1],
        })
        heatmap = hourly_demand(rows, rows)
        cell = heatmap.loc[heatmap.weekday_num.eq(0) & heatmap.hour.eq(10)].iloc[0]
        self.assertEqual(cell.observed_days, 2)
        self.assertEqual(cell.avg_drinks, 4.0)

    def test_zero_baseline_and_reversed_dates(self):
        self.assertIsNone(percent_change(12, 0))
        self.assertAlmostEqual(percent_change(120, 100), 20)
        with self.assertRaises(ValueError):
            make_period("2023-06-30", "2023-06-01")

    def test_invalid_source_requires_review(self):
        row = self.df.iloc[[0]][[
            "transaction_id", "transaction_date", "transaction_time", "transaction_qty",
            "store_id", "store_location", "product_id", "unit_price", "product_category",
            "product_type", "product_detail",
        ]].copy()
        task_temp = ROOT / ".test_tmp"
        task_temp.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=task_temp) as directory:
            path = Path(directory) / "invalid.csv"
            row.loc[:, "transaction_qty"] = 0
            row.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "positive whole numbers"):
                load_sales(path)
            row.loc[:, "transaction_qty"] = 1
            pd.concat([row, row]).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "Duplicate transaction IDs"):
                load_sales(path)


if __name__ == "__main__":
    unittest.main()
