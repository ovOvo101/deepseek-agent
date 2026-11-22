"""单店单笔订单优惠枚举，金额使用整数分。"""
import json
from decimal import Decimal, InvalidOperation


def money(value):
    if not isinstance(value, str) or len(value) > 20:
        raise ValueError('金额须为最多两位小数的字符串')
    try:
        number = Decimal(value)
        cents = number * 100
        if not number.is_finite() or number < 0 or number > 100000000 or cents != cents.to_integral_value():
            raise ValueError('金额须非负、最多两位小数且不超过一亿元')
        return int(cents)
    except InvalidOperation:
        raise ValueError('金额格式无效') from None


def fields(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError('规则字段不符合要求，请参照示例')


def optimize(config):
    fields(config, ['items', 'shipping', 'reductions', 'coupons', 'stackable', 'coupon_basis'])
    if type(config['stackable']) is not bool or config['coupon_basis'] not in ('original', 'after_reduction'):
        raise ValueError('须明确叠加开关及优惠券门槛计算口径')
    for key, limit in [('items', 100), ('reductions', 30), ('coupons', 30)]:
        if not isinstance(config[key], list) or len(config[key]) > limit:
            raise ValueError('商品最多100项、满减及优惠券各最多30项')
    if not config['items']:
        raise ValueError('至少需要一项商品')
    total = 0
    for item in config['items']:
        fields(item, ['name', 'price', 'quantity'])
        if not isinstance(item['name'], str) or not item['name'].strip() or type(item['quantity']) is not int or not 1 <= item['quantity'] <= 10000:
            raise ValueError('商品名称或数量无效')
        total += money(item['price']) * item['quantity']
    shipping = money(config['shipping'])
    reductions = [('不使用满减', 0)]
    coupons = [('不使用优惠券', 0, 0)]
    for rule in config['reductions']:
        fields(rule, ['name', 'threshold', 'discount', 'repeat'])
        threshold, discount = money(rule['threshold']), money(rule['discount'])
        if not isinstance(rule['name'], str) or not rule['name'].strip() or type(rule['repeat']) is not bool or threshold <= 0 or discount > threshold:
            raise ValueError('满减规则无效')
        count = total // threshold if rule['repeat'] else int(total >= threshold)
        reductions.append((rule['name'], min(total, count * discount)))
    for rule in config['coupons']:
        fields(rule, ['name', 'threshold', 'discount'])
        if not isinstance(rule['name'], str) or not rule['name'].strip():
            raise ValueError('优惠券名称无效')
        coupons.append((rule['name'], money(rule['threshold']), money(rule['discount'])))
    plans = []
    for ri, (reduction, amount) in enumerate(reductions):
        for ci, (coupon, threshold, discount) in enumerate(coupons):
            if ri and ci and not config['stackable']:
                continue
            basis = total if config['coupon_basis'] == 'original' else total - amount
            if basis < threshold:
                continue
            applied = min(total - amount, discount)
            payable = total - amount - applied + shipping
            plans.append({'满减': reduction, '优惠券': coupon, '满减优惠': amount, '券优惠': applied, '实付': payable})
    plans.sort(key=lambda p: p['实付'])
    best = plans[0]['实付']
    def display(plan):
        return {k: f'{Decimal(v) / 100:.2f}' if type(v) is int else v for k, v in plan.items()}
    return {'计算范围': '固定购物车、单店单笔；最多选一个满减规则和一张券；先满减再用券；运费固定且不参与优惠', '原商品金额': f'{Decimal(total) / 100:.2f}', '运费': f'{Decimal(shipping) / 100:.2f}', '最低实付': f'{Decimal(best) / 100:.2f}', '总优惠': f'{Decimal(total + shipping - best) / 100:.2f}', '最优方案': [display(p) for p in plans if p['实付'] == best][:10], '并列最优数量': sum(p['实付'] == best for p in plans), '展示说明': '最优方案及方案对比分别最多展示10项', '可行方案数量': len(plans), '方案对比': [display(p) for p in plans[:10]]}


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser()
    parser.add_argument('config', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(optimize(json.loads(args.config.read_text())), ensure_ascii=False, indent=2))
    except (ValueError, OSError) as error:
        parser.exit(1, f'规则无效：{error}\n')
