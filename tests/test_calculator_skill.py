"""
Real tests for calculator_skill.py

Every test calls the actual CalculatorSkill code.
No mocks — if the math is wrong, the test fails.
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.calculator_skill import CalculatorSkill


@pytest.fixture
def calc():
    return CalculatorSkill()


# ── calculate() ───────────────────────────────────────────────────────────────


class TestCalculate:
    def test_addition(self, calc):
        r = calc.calculate("2 + 3")
        assert r["success"] is True
        assert r["result"] == 5

    def test_subtraction(self, calc):
        r = calc.calculate("100 - 37")
        assert r["success"] is True
        assert r["result"] == 63

    def test_multiplication(self, calc):
        r = calc.calculate("500 * 12")
        assert r["success"] is True
        assert r["result"] == 6000

    def test_division(self, calc):
        r = calc.calculate("10 / 4")
        assert r["success"] is True
        assert abs(r["result"] - 2.5) < 1e-9

    def test_integer_division(self, calc):
        r = calc.calculate("10 // 3")
        assert r["success"] is True
        assert r["result"] == 3

    def test_modulo(self, calc):
        r = calc.calculate("17 % 5")
        assert r["success"] is True
        assert r["result"] == 2

    def test_exponentiation(self, calc):
        r = calc.calculate("2 ** 10")
        assert r["success"] is True
        assert r["result"] == 1024

    def test_nested_expression(self, calc):
        r = calc.calculate("(100 + 200) * 3 / 9")
        assert r["success"] is True
        assert abs(r["result"] - 100.0) < 1e-9

    def test_negative_unary(self, calc):
        r = calc.calculate("-5 + 10")
        assert r["success"] is True
        assert r["result"] == 5

    def test_sqrt_function(self, calc):
        r = calc.calculate("sqrt(144)")
        assert r["success"] is True
        assert r["result"] == 12.0

    def test_pi_constant(self, calc):
        r = calc.calculate("pi * 2")
        assert r["success"] is True
        import math
        assert abs(r["result"] - math.tau) < 1e-9

    def test_math_with_round(self, calc):
        r = calc.calculate("round(3.14159, 2)")
        assert r["success"] is True
        assert r["result"] == 3.14

    def test_abs_function(self, calc):
        r = calc.calculate("abs(-42)")
        assert r["success"] is True
        assert r["result"] == 42

    def test_division_by_zero_returns_error(self, calc):
        r = calc.calculate("10 / 0")
        assert r["success"] is False
        assert "zero" in r["error"].lower()

    def test_empty_expression_returns_error(self, calc):
        r = calc.calculate("")
        assert r["success"] is False

    def test_disallowed_function_blocked(self, calc):
        r = calc.calculate("__import__('os').system('ls')")
        assert r["success"] is False

    def test_open_call_blocked(self, calc):
        r = calc.calculate("open('/etc/passwd').read()")
        assert r["success"] is False

    def test_string_input_blocked(self, calc):
        r = calc.calculate("'hello'")
        assert r["success"] is False

    def test_formatted_result_integer(self, calc):
        r = calc.calculate("6 * 7")
        assert r["formatted"] == "42"

    def test_business_math_mrr(self, calc):
        # 3 clients × ₹5000/month = ₹15000
        r = calc.calculate("3 * 5000")
        assert r["success"] is True
        assert r["result"] == 15000

    def test_execute_routes_correctly(self, calc):
        r = calc.execute("calculate", {"expression": "10 + 5"})
        assert r["success"] is True
        assert r["result"] == 15

    def test_execute_unknown_tool_returns_error(self, calc):
        r = calc.execute("fly_to_moon", {})
        assert r["success"] is False
        assert "Unknown tool" in r["error"]


# ── calculate_mrr() ───────────────────────────────────────────────────────────


class TestCalculateMRR:
    def test_basic_mrr(self, calc):
        r = calc.calculate_mrr(clients=5, price_per_client=5000)
        assert r["success"] is True
        assert r["mrr_inr"] == 25000
        assert r["arr_inr"] == 300000

    def test_zero_clients(self, calc):
        r = calc.calculate_mrr(clients=0, price_per_client=5000)
        assert r["success"] is True
        assert r["mrr_inr"] == 0

    def test_string_inputs_parsed(self, calc):
        r = calc.calculate_mrr(clients="3", price_per_client="2500")
        assert r["success"] is True
        assert r["mrr_inr"] == 7500

    def test_negative_clients_rejected(self, calc):
        r = calc.calculate_mrr(clients=-1, price_per_client=1000)
        assert r["success"] is False

    def test_formatted_output_present(self, calc):
        r = calc.calculate_mrr(clients=1, price_per_client=5000)
        assert "₹" in r["mrr_formatted"]
        assert "₹" in r["arr_formatted"]


# ── calculate_revenue_target() ────────────────────────────────────────────────


class TestRevenueTarget:
    def test_10_lakh_at_5000_per_month(self, calc):
        # Target: ₹10,00,000 at ₹5000/client/month over 12 months
        r = calc.calculate_revenue_target(
            target_inr=1_000_000,
            price_per_client=5000,
            months=12,
        )
        assert r["success"] is True
        # 1000000 / (5000 * 12) = 16.67 → ceil = 17
        assert r["clients_needed"] == 17

    def test_zero_price_rejected(self, calc):
        r = calc.calculate_revenue_target(
            target_inr=100000, price_per_client=0, months=12
        )
        assert r["success"] is False

    def test_summary_string_present(self, calc):
        r = calc.calculate_revenue_target(100000, 5000, 12)
        assert r["success"] is True
        assert "clients" in r["summary"].lower()


# ── calculate_growth_rate() ───────────────────────────────────────────────────


class TestGrowthRate:
    def test_positive_growth(self, calc):
        r = calc.calculate_growth_rate(current_value=120, previous_value=100)
        assert r["success"] is True
        assert r["growth_rate_percent"] == 20.0
        assert r["direction"] == "up"

    def test_negative_growth(self, calc):
        r = calc.calculate_growth_rate(current_value=80, previous_value=100)
        assert r["success"] is True
        assert r["growth_rate_percent"] == -20.0
        assert r["direction"] == "down"

    def test_zero_growth(self, calc):
        r = calc.calculate_growth_rate(current_value=100, previous_value=100)
        assert r["success"] is True
        assert r["growth_rate_percent"] == 0.0
        assert r["direction"] == "flat"

    def test_from_zero_revenue(self, calc):
        r = calc.calculate_growth_rate(current_value=5000, previous_value=0)
        assert r["success"] is True
        assert r["direction"] == "up"
        assert r["growth_rate_percent"] is None  # infinite

    def test_both_zero_rejected(self, calc):
        r = calc.calculate_growth_rate(current_value=0, previous_value=0)
        assert r["success"] is False


# ── convert_units() ───────────────────────────────────────────────────────────


class TestConvertUnits:
    def test_inr_to_usd(self, calc):
        r = calc.convert_units(83.5, "inr", "usd")
        assert r["success"] is True
        assert r["type"] == "currency"
        assert abs(r["result"] - 1.0) < 0.01

    def test_gb_to_mb(self, calc):
        r = calc.convert_units(1, "gb", "mb")
        assert r["success"] is True
        assert r["type"] == "data"
        assert r["result"] == 1000  # 1 GB = 1000 MB (SI)

    def test_hours_to_minutes(self, calc):
        r = calc.convert_units(2, "hours", "minutes")
        assert r["success"] is True
        assert r["type"] == "time"
        assert r["result"] == 120

    def test_days_to_seconds(self, calc):
        r = calc.convert_units(1, "day", "seconds")
        assert r["success"] is True
        assert r["result"] == 86400

    def test_unknown_units_rejected(self, calc):
        r = calc.convert_units(100, "furlongs", "parsecs")
        assert r["success"] is False
        assert "Cannot convert" in r["error"]

    def test_non_numeric_value_rejected(self, calc):
        r = calc.convert_units("lots", "inr", "usd")
        assert r["success"] is False
