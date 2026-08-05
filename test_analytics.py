"""
test_analytics.py -- unit tests for the quant signals in analytics.py.

Each test uses a hand-built input where the correct answer is computable by
hand, so we assert exact values rather than "it ran".

Run:  python -m pytest test_analytics.py -v
      or  python test_analytics.py
"""

import math

from order_book import OrderBook, Side, Trade
from analytics import vwap, realized_volatility, order_book_imbalance


def _trade(price, size, aggressor=Side.BUY):
    return Trade(price=price, size=size, aggressor=aggressor,
                 maker_id=0, taker_id=0, seq=0)


# --- VWAP --------------------------------------------------------------------
def test_vwap_weights_by_size():
    # 10 @ 100  and  30 @ 104  ->  (10*100 + 30*104) / 40 = 103.0
    tape = [_trade(100.0, 10), _trade(104.0, 30)]
    assert vwap(tape) == 103.0


def test_vwap_single_trade_is_that_price():
    assert vwap([_trade(99.95, 7)]) == 99.95


def test_vwap_empty_tape_is_none():
    assert vwap([]) is None


# --- realized volatility -----------------------------------------------------
def test_realized_vol_flat_prices_is_zero():
    # constant price -> zero log returns -> zero volatility
    tape = [_trade(100.0, 1) for _ in range(5)]
    assert realized_volatility(tape) == 0.0


def test_realized_vol_matches_manual_std():
    prices = [100.0, 101.0, 100.0]
    tape = [_trade(p, 1) for p in prices]
    r = [math.log(101/100), math.log(100/101)]
    mean = sum(r) / len(r)
    expected = math.sqrt(sum((x - mean) ** 2 for x in r) / len(r))  # population std
    assert abs(realized_volatility(tape) - expected) < 1e-12


def test_realized_vol_needs_two_trades():
    assert realized_volatility([_trade(100.0, 1)]) is None
    assert realized_volatility([]) is None


# --- order-book imbalance ----------------------------------------------------
def test_obi_balanced_book_is_zero():
    b = OrderBook(0.01)
    b.submit_limit(Side.BUY, 99.99, 10)
    b.submit_limit(Side.SELL, 100.01, 10)
    assert order_book_imbalance(b) == 0.0


def test_obi_heavy_bid_is_positive():
    b = OrderBook(0.01)
    b.submit_limit(Side.BUY, 99.99, 30)    # bid-heavy
    b.submit_limit(Side.SELL, 100.01, 10)
    # (30 - 10) / (30 + 10) = 0.5
    assert order_book_imbalance(b) == 0.5


def test_obi_heavy_ask_is_negative():
    b = OrderBook(0.01)
    b.submit_limit(Side.BUY, 99.99, 10)
    b.submit_limit(Side.SELL, 100.01, 30)  # ask-heavy
    assert order_book_imbalance(b) == -0.5


def test_obi_empty_book_is_none():
    assert order_book_imbalance(OrderBook(0.01)) is None


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed.")
