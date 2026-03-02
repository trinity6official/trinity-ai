"""
Trinity Calculator Skill — Safe Mathematical Evaluator

Uses Python AST parsing instead of eval() — no arbitrary code execution.
Supports arithmetic, comparison, math functions, financial calculations,
unit conversions, and business math Trinity actually needs.
"""
import ast
import math
import operator
from datetime import datetime


class CalculatorSkill:
    """
    Safe math calculations using AST parsing.
    Never uses eval() or exec(). Only whitelisted AST nodes allowed.
    """

    name = "calculator"
    description = "Safe math calculations, financial analysis, unit conversions"

    _OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    # Only math functions — no builtins that could do I/O
    _FUNCTIONS = {
        'sqrt': math.sqrt,
        'abs': abs,
        'round': round,
        'floor': math.floor,
        'ceil': math.ceil,
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'log': math.log,
        'log10': math.log10,
        'log2': math.log2,
        'exp': math.exp,
        'pow': pow,
        'min': min,
        'max': max,
    }

    _CONSTANTS = {
        'pi': math.pi,
        'e': math.e,
        'inf': math.inf,
    }

    def get_tools(self):
        return [
            {
                "name": "calculate",
                "description": "Evaluate any math expression safely (e.g. '500 * 12 / 100')",
                "params": ["expression"],
                "needs_approval": False,
            },
            {
                "name": "calculate_mrr",
                "description": "Calculate Monthly Recurring Revenue from clients and price",
                "params": ["clients", "price_per_client"],
                "needs_approval": False,
            },
            {
                "name": "calculate_revenue_target",
                "description": "How many clients needed to hit a revenue target",
                "params": ["target_inr", "price_per_client", "months"],
                "needs_approval": False,
            },
            {
                "name": "calculate_growth_rate",
                "description": "Month-over-month or year-over-year growth percentage",
                "params": ["current_value", "previous_value"],
                "needs_approval": False,
            },
            {
                "name": "convert_units",
                "description": "Convert currency (inr/usd/eur), data (kb/mb/gb), time (hours/days)",
                "params": ["value", "from_unit", "to_unit"],
                "needs_approval": False,
            },
        ]

    def execute(self, tool_name, params):
        tool_map = {
            "calculate": self.calculate,
            "calculate_mrr": self.calculate_mrr,
            "calculate_revenue_target": self.calculate_revenue_target,
            "calculate_growth_rate": self.calculate_growth_rate,
            "convert_units": self.convert_units,
        }
        tool = tool_map.get(tool_name)
        if not tool:
            return {"error": f"Unknown tool: {tool_name}", "success": False}
        try:
            return tool(**params)
        except TypeError as e:
            return {"error": f"Wrong params for {tool_name}: {e}", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}

    # ==========================================
    # SAFE AST EVALUATOR
    # ==========================================

    def _eval_node(self, node):
        """Recursively evaluate an AST node. Only safe operations allowed."""
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)):
                raise ValueError(f"Only numbers allowed, got: {type(node.value).__name__}")
            return node.value

        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in self._OPERATORS:
                raise ValueError(f"Operator not allowed: {op_type.__name__}")
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            return self._OPERATORS[op_type](left, right)

        if isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in self._OPERATORS:
                raise ValueError(f"Unary operator not allowed: {op_type.__name__}")
            return self._OPERATORS[op_type](self._eval_node(node.operand))

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only simple function names allowed (no method calls)")
            name = node.func.id
            if name not in self._FUNCTIONS:
                raise ValueError(
                    f"Function '{name}' not allowed. "
                    f"Allowed: {sorted(self._FUNCTIONS)}"
                )
            args = [self._eval_node(a) for a in node.args]
            return self._FUNCTIONS[name](*args)

        if isinstance(node, ast.Name):
            if node.id in self._CONSTANTS:
                return self._CONSTANTS[node.id]
            raise ValueError(
                f"Unknown name '{node.id}'. "
                f"Known constants: {sorted(self._CONSTANTS)}"
            )

        raise ValueError(f"AST node type not allowed: {type(node).__name__}")

    # ==========================================
    # TOOLS
    # ==========================================

    def calculate(self, expression):
        """Safely evaluate a mathematical expression using AST."""
        expression = str(expression).strip()
        if len(expression) > 500:
            return {"error": "Expression too long (max 500 chars)", "success": False}
        if not expression:
            return {"error": "Empty expression", "success": False}

        try:
            tree = ast.parse(expression, mode='eval')
        except SyntaxError as e:
            return {
                "error": f"Syntax error in expression: {e}",
                "success": False,
                "expression": expression,
            }

        try:
            result = self._eval_node(tree.body)
        except ZeroDivisionError:
            return {"error": "Division by zero", "success": False, "expression": expression}
        except (ValueError, TypeError) as e:
            return {"error": str(e), "success": False, "expression": expression}
        except Exception as e:
            return {"error": f"Calculation failed: {e}", "success": False, "expression": expression}

        # Format output
        if isinstance(result, float):
            if result == int(result) and abs(result) < 1e15:
                formatted = str(int(result))
            else:
                formatted = f"{result:.10g}"
        else:
            formatted = str(result)

        return {
            "success": True,
            "expression": expression,
            "result": result,
            "formatted": formatted,
            "calculated_at": datetime.now().isoformat(),
        }

    def calculate_mrr(self, clients, price_per_client):
        """Calculate Monthly Recurring Revenue and Annual Run Rate."""
        try:
            n = float(clients)
            p = float(price_per_client)
            if n < 0 or p < 0:
                return {"error": "Clients and price must be non-negative", "success": False}
            mrr = n * p
            arr = mrr * 12
            return {
                "success": True,
                "clients": int(n),
                "price_per_client_inr": p,
                "mrr_inr": mrr,
                "arr_inr": arr,
                "mrr_formatted": f"₹{mrr:,.0f}/month",
                "arr_formatted": f"₹{arr:,.0f}/year",
            }
        except (ValueError, TypeError) as e:
            return {"error": f"Invalid input: {e}", "success": False}

    def calculate_revenue_target(self, target_inr, price_per_client, months=12):
        """How many clients do you need to hit a revenue target?"""
        try:
            target = float(target_inr)
            price = float(price_per_client)
            months = int(months)
            if price <= 0:
                return {"error": "Price per client must be positive", "success": False}
            if months <= 0:
                return {"error": "Months must be positive", "success": False}
            if target <= 0:
                return {"error": "Target must be positive", "success": False}

            clients_needed = math.ceil(target / (price * months))
            monthly_at_target = clients_needed * price

            return {
                "success": True,
                "target_inr": target,
                "target_formatted": f"₹{target:,.0f}",
                "price_per_client_inr": price,
                "months": months,
                "clients_needed": clients_needed,
                "monthly_revenue_at_target": monthly_at_target,
                "monthly_at_target_formatted": f"₹{monthly_at_target:,.0f}/month",
                "summary": (
                    f"Need {clients_needed} clients at ₹{price:,.0f}/month "
                    f"for {months} months to reach ₹{target:,.0f}"
                ),
            }
        except (ValueError, TypeError) as e:
            return {"error": f"Invalid input: {e}", "success": False}

    def calculate_growth_rate(self, current_value, previous_value):
        """Calculate growth rate as a percentage."""
        try:
            current = float(current_value)
            previous = float(previous_value)

            if previous == 0:
                if current > 0:
                    return {
                        "success": True,
                        "current": current,
                        "previous": previous,
                        "growth_rate_percent": None,
                        "direction": "up",
                        "summary": "Infinite growth — previous value was zero (new revenue!)",
                    }
                return {"error": "Both values are zero — no growth to calculate", "success": False}

            rate = ((current - previous) / abs(previous)) * 100
            direction = "up" if rate > 0 else "down" if rate < 0 else "flat"

            return {
                "success": True,
                "current": current,
                "previous": previous,
                "growth_rate_percent": round(rate, 2),
                "direction": direction,
                "summary": f"{abs(rate):.1f}% {direction}",
            }
        except (ValueError, TypeError) as e:
            return {"error": f"Invalid input: {e}", "success": False}

    def convert_units(self, value, from_unit, to_unit):
        """Convert between currency, data size, and time units."""
        try:
            value = float(value)
        except (ValueError, TypeError):
            return {"error": f"'{value}' is not a valid number", "success": False}

        from_u = str(from_unit).lower().strip()
        to_u = str(to_unit).lower().strip()

        # ── Currency (approximate mid-market rates) ──────────────────
        # Rates relative to USD
        _CURRENCY = {
            'usd': 1.0,
            'inr': 1 / 83.5,
            'eur': 1 / 0.92,
            'gbp': 1 / 0.79,
            'sgd': 1 / 1.34,
            'aed': 1 / 3.67,
            'jpy': 1 / 149.5,
        }
        if from_u in _CURRENCY and to_u in _CURRENCY:
            usd = value * _CURRENCY[from_u]
            result = usd / _CURRENCY[to_u]
            return {
                "success": True,
                "type": "currency",
                "input": f"{value} {from_u.upper()}",
                "result": round(result, 4),
                "output": f"{result:.2f} {to_u.upper()}",
                "note": "Approximate mid-market rate — verify before financial decisions.",
            }

        # ── Data size (to bytes) ──────────────────────────────────────
        _DATA = {
            'b': 1,
            'kb': 1000, 'kib': 1024,
            'mb': 1000**2, 'mib': 1024**2,
            'gb': 1000**3, 'gib': 1024**3,
            'tb': 1000**4, 'tib': 1024**4,
        }
        if from_u in _DATA and to_u in _DATA:
            bytes_val = value * _DATA[from_u]
            result = bytes_val / _DATA[to_u]
            return {
                "success": True,
                "type": "data",
                "input": f"{value} {from_u.upper()}",
                "result": result,
                "output": f"{result:.6g} {to_u.upper()}",
            }

        # ── Time (to seconds) ─────────────────────────────────────────
        _TIME = {
            'second': 1, 'seconds': 1, 's': 1,
            'minute': 60, 'minutes': 60, 'min': 60,
            'hour': 3600, 'hours': 3600, 'h': 3600,
            'day': 86400, 'days': 86400,
            'week': 604800, 'weeks': 604800,
            'month': 2_592_000, 'months': 2_592_000,
            'year': 31_536_000, 'years': 31_536_000,
        }
        if from_u in _TIME and to_u in _TIME:
            seconds = value * _TIME[from_u]
            result = seconds / _TIME[to_u]
            return {
                "success": True,
                "type": "time",
                "input": f"{value} {from_u}",
                "result": result,
                "output": f"{result:.6g} {to_u}",
            }

        return {
            "error": (
                f"Cannot convert '{from_unit}' to '{to_unit}'. "
                "Supported groups — "
                "currency: usd/inr/eur/gbp/sgd/aed/jpy, "
                "data: b/kb/mb/gb/tb, "
                "time: seconds/minutes/hours/days/weeks/months/years"
            ),
            "success": False,
        }
