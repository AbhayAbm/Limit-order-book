"""
market_sim.py — a toy stochastic order-flow generator.

This drives the order book so there is something to watch. It is deliberately
simple: a single "fair value" random walk that agents quote around. It is not a
realistic market microstructure model — it just produces a plausibly busy book.

Model
-----
  * Fair value:   fv += drift + Normal(0, sigma)      each step.
  * Each step, three independent Poisson-like coin flips decide whether to:
      - post a LIMIT order near fv (rate `limit_rate`),
      - fire a MARKET order (rate `market_rate`),
      - CANCEL a random resting order (rate `cancel_rate`).
  * `aggressiveness` biases limit prices toward (or across) the spread, so
    higher values mean more crossing / trading.

Everything uses the standard-library `random`, seeded for reproducibility.
"""

from __future__ import annotations

import random

from order_book import OrderBook, Side


class MarketSimulator:
    def __init__(
        self,
        book: OrderBook,
        fair_value: float = 100.00,
        drift: float = 0.0,
        sigma: float = 0.02,
        limit_rate: float = 0.9,
        market_rate: float = 0.15,
        cancel_rate: float = 0.3,
        aggressiveness: float = 0.35,
        max_spread_ticks: int = 12,
        seed: int | None = 7,
    ):
        self.book = book
        self.fv = fair_value
        self.drift = drift
        self.sigma = sigma
        self.limit_rate = limit_rate
        self.market_rate = market_rate
        self.cancel_rate = cancel_rate
        self.aggressiveness = aggressiveness
        self.max_spread_ticks = max_spread_ticks
        self.rng = random.Random(seed)
        self._live_ids: list[int] = []

    # ---- one simulation tick -------------------------------------------------------

    def step(self) -> list:
        """Advance fair value and fire off a random burst of orders/cancels.

        Returns the list of Trades produced this step (for the tape/GUI).
        """
        self.fv += self.drift + self.rng.gauss(0.0, self.sigma)
        trades = []

        if self.rng.random() < self.limit_rate:
            trades += self._post_limit()
        if self.rng.random() < self.market_rate:
            trades += self._fire_market()
        if self.rng.random() < self.cancel_rate:
            self._cancel_random()

        return trades

    # ---- individual agent actions --------------------------------------------------

    def _post_limit(self) -> list:
        side = self.rng.choice([Side.BUY, Side.SELL])
        # Offset from fair value: usually inside a few ticks; aggressiveness pulls
        # the quote toward/across the mid so it is more likely to cross and trade.
        offset_ticks = self.rng.randint(0, self.max_spread_ticks)
        offset = offset_ticks * self.book.tick_size
        if self.rng.random() < self.aggressiveness:
            offset = -offset          # cross the fair value -> marketable

        price = self.fv + offset if side == Side.BUY else self.fv - offset
        price = max(self.book.tick_size, round(price, 10))
        qty = self.rng.randint(1, 25)

        order, trades = self.book.submit_limit(side, price, qty)
        if order.remaining > 0:
            self._live_ids.append(order.id)
        return trades

    def _fire_market(self) -> list:
        side = self.rng.choice([Side.BUY, Side.SELL])
        qty = self.rng.randint(1, 15)
        _, trades = self.book.submit_market(side, qty)
        return trades

    def _cancel_random(self) -> None:
        # Drop stale ids lazily; cancel one order that is still live.
        while self._live_ids:
            oid = self._live_ids.pop(self.rng.randrange(len(self._live_ids)))
            if oid in self.book.orders:
                self.book.cancel(oid)
                return

    # ---- convenience ---------------------------------------------------------------

    def warmup(self, steps: int = 200) -> None:
        """Run a burst of steps to build a two-sided book before display."""
        for _ in range(steps):
            self.step()


if __name__ == "__main__":
    # Quick demo: warm up a book and print the top of the market.
    ob = OrderBook(tick_size=0.01)
    sim = MarketSimulator(ob)
    sim.warmup(300)
    print("best bid:", ob.best_bid(), "best ask:", ob.best_ask())
    print("mid:", ob.mid(), "spread(ticks):", ob.spread())
    print("bid depth:", ob.depth(Side.BUY, 5))
    print("ask depth:", ob.depth(Side.SELL, 5))
