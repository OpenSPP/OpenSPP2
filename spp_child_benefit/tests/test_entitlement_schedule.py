# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestScheduleMath(TransactionCase):
    """Table-driven tests for the benefit schedule generator (15th-Day Rule).

    Business rules under test:
    - born on or before the cutoff day (15th): full entry month, prorated exit month;
    - born after the cutoff day: prorated entry month, full exit month;
    - a schedule is never prorated at both ends;
    - every intermediate calendar month is the full monthly amount;
    - the daily rate is the monthly amount / days in that month, rounded to 2dp
      (30-day months: 333.33; 31-day months: 322.58);
    - each installment is rounded to 2dp independently;
    - no prorated installment may exceed the full monthly amount.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Schedule = cls.env["spp.entitlement.schedule"]
        cls.params = {
            "monthly_amount": 10000.0,
            "age_limit_months": 36,
            "cutoff_day": 15,
        }

    def _lines(self, birthdate):
        return self.Schedule._compute_schedule_lines(birthdate, **self.params)

    def test_born_on_or_before_cutoff_31_day_month(self):
        # Born 10 July 2026 -> full entry month; attains 36 months 10 July 2029
        # -> exit month prorated to 10 days at the 31-day rate 322.58.
        lines = self._lines(date(2026, 7, 10))
        self.assertEqual(len(lines), 37)  # birth month .. attainment month inclusive
        first, last = lines[0], lines[-1]
        self.assertEqual(first["benefit_month"], date(2026, 7, 1))
        self.assertEqual(first["amount"], 10000.0)
        self.assertEqual(first["proration"], "none")
        self.assertEqual(last["benefit_month"], date(2029, 7, 1))
        self.assertEqual(last["proration"], "exit")
        self.assertEqual(last["days_payable"], 10)
        self.assertEqual(last["daily_rate"], 322.58)
        self.assertEqual(last["amount"], 3225.80)
        for line in lines[1:-1]:
            self.assertEqual(line["amount"], 10000.0)
            self.assertEqual(line["proration"], "none")

    def test_born_after_cutoff_31_day_month(self):
        # Born 20 July 2026 -> entry prorated for 20..31 July inclusive (12 days);
        # final month is paid in full.
        lines = self._lines(date(2026, 7, 20))
        first, last = lines[0], lines[-1]
        self.assertEqual(first["proration"], "entry")
        self.assertEqual(first["days_payable"], 12)
        self.assertEqual(first["amount"], 3870.96)  # 12 * 322.58
        self.assertEqual(last["benefit_month"], date(2029, 7, 1))
        self.assertEqual(last["proration"], "none")
        self.assertEqual(last["amount"], 10000.0)

    def test_cutoff_boundary_day_15_vs_16(self):
        # 15th (30-day month): full entry, prorated exit of 15 days at 333.33
        lines_15 = self._lines(date(2026, 9, 15))
        self.assertEqual(lines_15[0]["proration"], "none")
        self.assertEqual(lines_15[-1]["proration"], "exit")
        self.assertEqual(lines_15[-1]["days_payable"], 15)
        self.assertEqual(lines_15[-1]["amount"], 4999.95)  # 15 * 333.33
        # 16th: prorated entry of 15 days (16..30), full exit
        lines_16 = self._lines(date(2026, 9, 16))
        self.assertEqual(lines_16[0]["proration"], "entry")
        self.assertEqual(lines_16[0]["days_payable"], 15)
        self.assertEqual(lines_16[0]["amount"], 4999.95)
        self.assertEqual(lines_16[-1]["proration"], "none")
        self.assertEqual(lines_16[-1]["amount"], 10000.0)

    def test_february_daily_rate(self):
        # Born 20 Feb 2027 (28-day month): rate 357.14, 9 days payable (20..28).
        lines = self._lines(date(2027, 2, 20))
        first = lines[0]
        self.assertEqual(first["proration"], "entry")
        self.assertEqual(first["daily_rate"], 357.14)
        self.assertEqual(first["days_payable"], 9)
        self.assertEqual(first["amount"], 3214.26)

    def test_never_prorated_at_both_ends(self):
        for birthdate in (date(2026, 7, 10), date(2026, 7, 20), date(2026, 9, 15), date(2026, 9, 16)):
            lines = self._lines(birthdate)
            prorated = [line for line in lines if line["proration"] != "none"]
            self.assertLessEqual(len(prorated), 1, f"birthdate {birthdate}: prorated at both ends")
            for line in lines:
                self.assertLessEqual(line["amount"], self.params["monthly_amount"])

    def test_every_month_contiguous(self):
        lines = self._lines(date(2026, 7, 20))
        months = [line["benefit_month"] for line in lines]
        for prev, cur in zip(months, months[1:], strict=False):
            next_month = date(prev.year + (prev.month == 12), prev.month % 12 + 1, 1)
            self.assertEqual(cur, next_month)

    def test_invalid_inputs_rejected(self):
        with self.assertRaises(ValidationError):
            self.Schedule._compute_schedule_lines(False, **self.params)
        with self.assertRaises(ValidationError):
            self.Schedule._compute_schedule_lines(
                date(2026, 7, 10), monthly_amount=0, age_limit_months=36, cutoff_day=15
            )
