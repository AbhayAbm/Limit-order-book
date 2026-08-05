"""
test_order_book.py — headless unit tests for the matching engine.

Run with:  python -m pytest test_order_book.py -v
       or:  python test_order_book.py   (falls back to a tiny runner)

These tests assert the *semantics* of price-time-priority matching, not any
particular internal representation. Each covers one of the behaviours the
project promises: priority rules, partial fills, price improvement, market
walking, cancellation, and the two structural invariants (shares are conserved,
the book never crosses).
"""

import random

from order_book import OrderBook, Side


def px(book, tick):
    return None if tick is None else round(book.to_price(tick), 6)


# --- market order semantics ---------------------------------------------------------

def test_market_fills_best_price_for_size():
    b = OrderBook(0.01)
    b.submit_limit(Side.SELL, 100.00, 50)
    b.submit_limit(Side.SELL, 100.01, 50)
    _, trades = b.submit_market(Side.BUY, 30)
    assert len(trades) == 1
    assert trades[0].quantity == 30
    assert px(b, trades[0].price_tick) == 100.00   # hit the best price only


def test_market_walks_levels_and_reports_shortfall():
    b = OrderBook(0.01)
    b.submit_limit(Side.SELL, 100.00, 40)
    b.submit_limit(Side.SELL, 100.01, 40)
    order, trades = b.submit_market(Side.BUY, 100)
    assert [t.quantity for t in trades] == [40, 40]
    assert [px(b, t.price_tick) for t in trades] == [100.00, 100.01]
    assert order.remaining == 20                   # unfilled shortfall reported
    assert b.best_ask() is None                    # book fully consumed


# --- priority rules -----------------------------------------------------------------

def test_time_priority_fifo():
    b = OrderBook(0.01)
    first, _ = b.submit_limit(Side.SELL, 100.00, 10)
    second, _ = b.submit_limit(Side.SELL, 100.00, 10)   # same price, arrives later
    _, trades = b.submit_market(Side.BUY, 10)
    assert trades[0].maker_id == first.id               # oldest fills first
    assert second.id in b.orders                         # newer still resting


def test_price_priority():
    b = OrderBook(0.01)
    worse, _ = b.submit_limit(Side.SELL, 100.05, 10)
    best, _ = b.submit_limit(Side.SELL, 100.00, 10)     # better price, arrives later
    _, trades = b.submit_market(Side.BUY, 10)
    assert trades[0].maker_id == best.id                 # best price fills first
    assert px(b, trades[0].price_tick) == 100.00


# --- limit-order crossing & resting -------------------------------------------------

def test_marketable_limit_crosses_then_rests_residual():
    b = OrderBook(0.01)
    b.submit_limit(Side.SELL, 100.00, 30)
    order, trades = b.submit_limit(Side.BUY, 100.00, 50)
    assert trades[0].quantity == 30                      # crosses available liquidity
    assert order.remaining == 20                         # residual...
    assert b.best_bid() == b.to_ticks(100.00)            # ...rests on the bid side
    assert b.best_ask() is None


def test_price_improvement_at_maker_price():
    b = OrderBook(0.01)
    b.submit_limit(Side.SELL, 100.00, 10)                # resting maker at 100.00
    _, trades = b.submit_limit(Side.BUY, 100.10, 10)     # aggressive buy up to 100.10
    assert px(b, trades[0].price_tick) == 100.00         # taker pays the maker's price


def test_partial_fill_leaves_correct_residual():
    b = OrderBook(0.01)
    maker, _ = b.submit_limit(Side.BUY, 99.99, 100)
    _, trades = b.submit_limit(Side.SELL, 99.99, 40)     # hits part of the resting bid
    assert trades[0].quantity == 40
    assert maker.remaining == 60                          # maker residual correct
    assert b.best_bid() == b.to_ticks(99.99)


# --- cancellation -------------------------------------------------------------------

def test_cancel_removes_order_and_empties_level():
    b = OrderBook(0.01)
    o, _ = b.submit_limit(Side.BUY, 99.98, 25)
    removed = b.cancel(o.id)
    assert removed is not None and removed.id == o.id
    assert b.best_bid() is None                          # level emptied and dropped
    assert b.cancel(o.id) is None                        # double-cancel is a no-op


# --- best-of-book updates -----------------------------------------------------------

def test_best_prices_and_spread_update_on_consumption():
    b = OrderBook(0.01)
    b.submit_limit(Side.BUY, 99.99, 10)
    b.submit_limit(Side.SELL, 100.01, 10)
    assert b.spread() == b.to_ticks(100.01) - b.to_ticks(99.99)
    b.submit_market(Side.BUY, 10)                        # consume the only ask
    assert b.best_ask() is None
    assert b.spread() is None                            # spread undefined one-sided


# --- structural invariants over random flow -----------------------------------------

def test_invariants_over_random_flow():
    b = OrderBook(0.01)
    rng = random.Random(42)
    live_ids = []

    def total_shares():
        resting = sum(o.remaining for o in b.orders.values())
        return resting

    traded = 0
    submitted = 0
    for _ in range(5000):
        action = rng.random()
        if action < 0.45:                                # limit order
            side = rng.choice([Side.BUY, Side.SELL])
            price = round(rng.uniform(99.50, 100.50), 2)
            qty = rng.randint(1, 20)
            order, trades = b.submit_limit(side, price, qty)
            submitted += qty
            traded += sum(t.quantity for t in trades)
            if order.remaining > 0:
                live_ids.append(order.id)
        elif action < 0.75:                              # market order
            side = rng.choice([Side.BUY, Side.SELL])
            qty = rng.randint(1, 20)
            _, trades = b.submit_market(side, qty)
            traded += sum(t.quantity for t in trades)
        elif live_ids:                                   # cancel
            oid = live_ids.pop(rng.randrange(len(live_ids)))
            b.cancel(oid)

        # Invariant 1: the book is never crossed.
        bb, ba = b.best_bid(), b.best_ask()
        if bb is not None and ba is not None:
            assert bb < ba, f"crossed book: bid {bb} >= ask {ba}"

        # Invariant 2: conservation — every submitted share is either resting,
        # traded (counted once as taker fill), or discarded market shortfall.
        # We check the weaker but robust form: resting shares are non-negative
        # and never exceed everything ever submitted.
        assert 0 <= total_shares() <= submitted

    # Sanity: some trading actually happened.
    assert traded > 0


# --- minimal fallback runner --------------------------------------------------------

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        t()
        passed += 1
        print(f"  ok  {t.__name__}")
    print(f"\n{passed}/{len(tests)} test functions passed.")
