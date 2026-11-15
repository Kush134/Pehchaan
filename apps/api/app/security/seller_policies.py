"""Private seller-owned policies. Never serialize these to buyer APIs or AI prompts."""
from decimal import Decimal

# Each seller owns unit floors, maximum authorized concessions and stock limits.
SELLER_POLICIES = {
    'seller-a': {'factor': Decimal('1.02'), 'floor_factor': Decimal('.84'), 'max_discount': 12,
                 'stock': {'rice': 250, 'atta': 300, 'oil': 150, 'snacks': 500, 'tea': 100}},
    'seller-b': {'factor': Decimal('1.05'), 'floor_factor': Decimal('.85'), 'max_discount': 14,
                 'stock': {'rice': 180, 'atta': 240, 'oil': 200, 'snacks': 400, 'tea': 120}},
    'seller-c': {'factor': Decimal('.99'), 'floor_factor': Decimal('.86'), 'max_discount': 10,
                 'stock': {'rice': 200, 'atta': 180, 'oil': 130, 'snacks': 600, 'tea': 80}},
}

def seller_floor(seller_id: str, products: list[dict], base_prices: dict[str, dict]) -> Decimal:
    policy = SELLER_POLICIES[seller_id]
    return sum((Decimal(str(base_prices[p['product_id']]['price'])) * Decimal(str(p['quantity'])) *
                policy['floor_factor'] for p in products), Decimal('0')).quantize(Decimal('.01'))
