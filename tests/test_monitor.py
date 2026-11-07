import unittest

from origin_guard.monitor import (
    EvaluationItem,
    estimate_cost,
    order_fingerprint,
    parse_score,
    shuffled_items,
)


class MonitorTests(unittest.TestCase):
    def test_parse_score(self):
        self.assertEqual(parse_score("<reasoning>x</reasoning><score>73</score>"), 73)

    def test_parse_score_rejects_multiple(self):
        with self.assertRaises(ValueError):
            parse_score("<score>1</score><score>2</score>")

    def test_cost_is_a_cap_using_maximum_output(self):
        item = EvaluationItem("i", "c", "target", "attack", "base", "abcd", "efgh")
        result = estimate_cost(
            [item],
            max_output_tokens=1000,
            input_price_per_million=2,
            output_price_per_million=10,
        )
        self.assertEqual(result["calls"], 1)
        self.assertAlmostEqual(result["estimated_maximum_cost_usd"], 0.010004)

    def test_shuffle_is_seeded_and_fingerprinted(self):
        items = [
            EvaluationItem(str(index), "c", "target", "attack", "base", "p", "m")
            for index in range(10)
        ]
        first = shuffled_items(items, seed=7)
        second = shuffled_items(items, seed=7)
        other = shuffled_items(items, seed=8)
        self.assertEqual([item.item_id for item in first], [item.item_id for item in second])
        self.assertNotEqual([item.item_id for item in first], [item.item_id for item in other])
        self.assertEqual(order_fingerprint(first), order_fingerprint(second))
        self.assertEqual([item.item_id for item in items], [str(index) for index in range(10)])


if __name__ == "__main__":
    unittest.main()
