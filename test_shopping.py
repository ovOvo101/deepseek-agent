"""优惠规则边界与 Agent 工具集成测试。"""
import json
import unittest
from pathlib import Path
from shopping import optimize
from agent import run
from test_agent import plan, response


class ShoppingTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((Path(__file__).parent / 'shopping.example.json').read_text())

    def test_after_reduction(self):
        result = optimize(self.config)
        self.assertEqual(result['最低实付'], '336.00')
        self.assertEqual(result['最优方案'][0]['优惠券'], '满300减30')

    def test_original_threshold(self):
        self.config['coupon_basis'] = 'original'
        self.assertEqual(optimize(self.config)['最低实付'], '326.00')

    def test_exclusive(self):
        self.config['stackable'] = False
        self.assertEqual(optimize(self.config)['最低实付'], '366.00')

    def test_repeat_and_cents(self):
        self.config['items'] = [{'name': '商品', 'price': '300.01', 'quantity': 2}]
        self.config['coupons'] = []
        self.assertEqual(optimize(self.config)['最低实付'], '508.02')
        self.config['reductions'][0]['repeat'] = False
        self.assertEqual(optimize(self.config)['最低实付'], '558.02')

    def test_discount_floor(self):
        self.config['coupons'] = [{'name': '大额券', 'threshold': '0', 'discount': '999'}]
        self.assertEqual(optimize(self.config)['最低实付'], '8.00')

    def test_invalid_rules(self):
        for invalid in ['NaN', '-1', '1.001']:
            self.config['shipping'] = invalid
            with self.assertRaises(ValueError):
                optimize(self.config)

    def test_agent_fixed_rules(self):
        replies = iter([plan(), response({'tool_calls': [{'id': 'discount', 'type': 'function', 'function': {'name': 'optimize_discounts', 'arguments': '{}'}}]}), plan(), response({'content': '最低实付336元'}), plan(True)])
        bodies = []
        def call(body):
            bodies.append(json.loads(json.dumps(body)))
            return next(replies)
        self.assertEqual(run('求最大优惠', '模拟', call, shopping=self.config), '最低实付336元')
        observations = [m for body in bodies for m in body['messages'] if m['role'] == 'tool']
        self.assertTrue(any(json.loads(m['content'])['result']['最低实付'] == '336.00' for m in observations))


if __name__ == '__main__':
    unittest.main()
