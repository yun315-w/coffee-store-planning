from datetime import date
from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class DashboardTests(unittest.TestCase):
    def test_default_view_and_store_filter(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 3)
        self.assertEqual(app.selectbox[0].value, "Lower Manhattan")
        self.assertEqual(app.date_input[0].value, (date(2023, 6, 3), date(2023, 6, 30)))
        self.assertEqual(len(app.get("vega_lite_chart")), 2)
        before = [metric.value for metric in app.metric]
        app.selectbox[0].select("Astoria").run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 3)
        self.assertNotEqual(before, [metric.value for metric in app.metric])

    def test_early_dates_hide_incomplete_comparison(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        app.date_input[0].set_value((date(2023, 1, 1), date(2023, 1, 7))).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 3)
        self.assertTrue(all(not metric.delta for metric in app.metric))
        self.assertTrue(any("Comparison unavailable" in caption.value for caption in app.caption))

    def test_single_day_and_pending_range(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        app.date_input[0].set_value((date(2023, 6, 30), date(2023, 6, 30))).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 3)
        app.date_input[0].set_value((date(2023, 6, 30),)).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 0)
        self.assertTrue(any("Choose an end date" in info.value for info in app.info))


if __name__ == "__main__":
    unittest.main()
