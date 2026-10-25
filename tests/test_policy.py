"""Policy tests: z-values, safety stock, reorder point, EOQ, orders."""

import math

import pytest

from supply_chain.policy import (
    eoq,
    recommend,
    reorder_point,
    safety_stock,
    z_for_service_level,
)


def test_z_table_and_interpolation():
    assert z_for_service_level(0.95) == pytest.approx(1.65)
    assert z_for_service_level(0.90) == pytest.approx(1.28)
    assert z_for_service_level(0.99) == pytest.approx(2.33)
    # Midpoint between 0.95 and 0.98 interpolates.
    assert z_for_service_level(0.965) == pytest.approx((1.65 + 2.05) / 2)
    assert z_for_service_level(0.50) == pytest.approx(1.28)  # clamped low
    assert z_for_service_level(1.00) == pytest.approx(2.33)  # clamped high


def test_safety_stock_scales_with_lead_time():
    base = safety_stock(10.0, 4.0, 0.95)
    assert base == pytest.approx(1.65 * 10 * 2.0)
    assert safety_stock(10.0, 9.0, 0.95) == pytest.approx(1.5 * base)
    with pytest.raises(ValueError):
        safety_stock(-1.0, 4.0, 0.95)


def test_reorder_point_is_demand_during_lead_time_plus_safety():
    assert reorder_point(100.0, 5.0, 50.0) == pytest.approx(550.0)


def test_eoq_formula():
    assert eoq(36500, 250.0, 2.0) == pytest.approx(
        math.sqrt(2 * 36500 * 250 / 2))
    with pytest.raises(ValueError):
        eoq(0, 250.0, 2.0)


def test_recommend_orders_when_below_rop_and_not_when_above():
    low = recommend("SKU-001", "STO-1", 100.0, 10.0, 5.0, 0.95,
                    250.0, 2.0, on_hand=100.0)
    assert low.order_quantity > 0
    assert any("reorder point" in r for r in low.reasons)
    high = recommend("SKU-001", "STO-1", 100.0, 10.0, 5.0, 0.95,
                     250.0, 2.0, on_hand=10000.0)
    assert high.order_quantity == 0.0
    assert any("above reorder point" in r for r in high.reasons)


def test_higher_service_level_means_more_safety_stock():
    low = recommend("SKU-001", "STO-1", 100.0, 10.0, 5.0, 0.90,
                    250.0, 2.0, on_hand=0.0)
    high = recommend("SKU-001", "STO-1", 100.0, 10.0, 5.0, 0.99,
                     250.0, 2.0, on_hand=0.0)
    assert high.safety_stock > low.safety_stock
    assert high.reorder_point > low.reorder_point
