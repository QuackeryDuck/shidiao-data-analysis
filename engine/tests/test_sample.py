"""样本量公式与边界测试。"""

from __future__ import annotations

import math
import unittest

from engine.sample import calculate, sensitivity_table, z_value


class SampleSizeTest(unittest.TestCase):
    def test_default_formula(self):
        r = calculate(confidence=0.95, margin_error=0.05, proportion=0.5, design_effect=1.0, response_rate=1.0)
        expected = (1.96 ** 2) * 0.25 / (0.05 ** 2)
        self.assertAlmostEqual(r.n_base, expected, places=6)
        self.assertEqual(r.n_base_rounded, math.ceil(expected))
        self.assertEqual(r.n_effective, math.ceil(expected))
        self.assertFalse(r.fpc_applied)

    def test_design_effect_and_response_rate(self):
        r = calculate(confidence=0.95, margin_error=0.05, proportion=0.5, design_effect=1.2, response_rate=0.85)
        self.assertEqual(r.n_effective, math.ceil(r.n_base * 1.2))
        self.assertEqual(r.n_plan, math.ceil(r.n_effective / 0.85))
        self.assertGreaterEqual(r.expected_valid, r.n_effective - 1)
        self.assertLessEqual(r.expected_valid, r.n_plan)

    def test_finite_population_correction(self):
        r = calculate(confidence=0.95, margin_error=0.05, proportion=0.5, population_size=1000)
        expected = r.n_base / (1 + (r.n_base - 1) / 1000)
        self.assertTrue(r.fpc_applied)
        self.assertAlmostEqual(r.n_fpc or 0, expected, places=6)
        self.assertLess(r.n_effective, math.ceil(r.n_base))

    def test_large_population_approaches_infinite(self):
        small = calculate(population_size=1_000_000)
        infinite = calculate(population_size=None)
        self.assertAlmostEqual(small.n_fpc or 0, infinite.n_base, delta=0.5)

    def test_clamps_invalid_parameters(self):
        r = calculate(confidence=2.0, margin_error=0.0, proportion=1.5, design_effect=0.5, response_rate=0.0)
        self.assertLessEqual(r.confidence, 0.999)
        self.assertGreaterEqual(r.margin_error, 0.001)
        self.assertLessEqual(r.proportion, 0.99)
        self.assertGreaterEqual(r.design_effect, 1.0)
        self.assertGreaterEqual(r.response_rate, 0.05)

    def test_z_values(self):
        self.assertAlmostEqual(z_value(0.95), 1.96)
        self.assertAlmostEqual(z_value(0.99), 2.576)
        self.assertGreater(z_value(0.99), z_value(0.90))

    def test_sensitivity_table_shape(self):
        rows = sensitivity_table([0.90, 0.95, 0.99], [0.04, 0.05], 0.5, 100000, 1.2, 0.9)
        self.assertEqual(len(rows), 6)
        self.assertTrue(all("n_plan" in row and "n_effective" in row for row in rows))
        self.assertTrue(all(row["n_plan"] >= row["n_effective"] for row in rows))


if __name__ == "__main__":
    unittest.main()
