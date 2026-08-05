"""
order_book.py — a price-time-priority limit order book matching engine.

This module is a *pure* engine: no printing, no GUI, no randomness. Everything
that happens is a deterministic consequence of the orders you submit, which is
exactly what makes it unit-testable.

Design in three sentences:
  * Prices are stored as integer "ticks" (price / tick_size, rounded) so the
    sorted keys are exact and the book can never silently cross due to float
    drift.
  * Each side of the book is a SortedDict keyed by tick -> price level, giving
    O(log L) access to the best price and an ordered walk for market orders.
  * Each price level is an OrderedDict keyed by order id, giving FIFO (time)
    priority with O(1) front access and O(1) cancellation.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from itertools import count

from sortedcontainers import SortedDict


class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Order:
    """A resting or incoming order. `remaining` shrinks as the order fills."""
    id: int
    side: Side
    price_tick: int          # integer price in ticks (None-like for market: unused)
    quantity: int            # original submitted quantity
    remaining: int           # unfilled quantity still live in the book

    @property
    def filled(self) -> int:
        return self.quantity - self.remaining


@dataclass
class Trade:
    """A single execution. Prints at the resting maker's price."""
    price_tick: int
    quantity: int
    taker_side: Side         # aggressor side
    maker_id: int
    taker_id: int


class OrderBook:
    """
    A limit order book with price-time-priority matching.

    Parameters
    ----------
    tick_size : float
        The minimum price increment. Prices are quantized to this so internal
        keys are exact integers. e.g. tick_size=0.01 -> price 100.05 is tick 10005.
    """

    def __init__(self, tick_size: float = 0.01):
        self.tick_size = tick_size
        # bids: highest price is "best", so we read from the largest key.
        # asks: lowest price is "best", so we read from the smallest key.
        self.bids: SortedDict[int, "OrderedDict[int, Order]"] = SortedDict()
        self.asks: SortedDict[int, "OrderedDict[int, Order]"] = SortedDict()
        # order_id -> Order, for O(1) lookup and cancellation.
        self.orders: dict[int, Order] = {}
        self._ids = count(1)

    # ---- price <-> tick conversion -------------------------------------------------

    def to_ticks(self, price: float) -> int:
        """Quantize a float price to an integer number of ticks."""
        return int(round(price / self.tick_size))

    def to_price(self, tick: int) -> float:
        """Convert an integer tick back to a float price."""
        return tick * self.tick_size

    # ---- best-of-book views --------------------------------------------------------

    def best_bid(self) -> int | None:
        """Highest bid tick, or None if there are no bids."""
        return self.bids.peekitem(-1)[0] if self.bids else None

    def best_ask(self) -> int | None:
        """Lowest ask tick, or None if there are no asks."""
        return self.asks.peekitem(0)[0] if self.asks else None

    def spread(self) -> int | None:
        """Best ask - best bid, in ticks. None if either side is empty."""
        bb, ba = self.best_bid(), self.best_ask()
        if bb is None or ba is None:
            return None
        return ba - bb

    def mid(self) -> float | None:
        """Mid price in float terms, or None if either side is empty."""
        bb, ba = self.best_bid(), self.best_ask()
        if bb is None or ba is None:
            return None
        return (self.to_price(bb) + self.to_price(ba)) / 2.0

    # ---- internal book maintenance -------------------------------------------------

    def _book_for(self, side: Side) -> "SortedDict[int, OrderedDict[int, Order]]":
        return self.bids if side == Side.BUY else self.asks

    def _rest(self, order: Order) -> None:
        """Insert an order's residual onto its own side of the book (FIFO tail)."""
        book = self._book_for(order.side)
        level = book.get(order.price_tick)
        if level is None:
            level = OrderedDict()
            book[order.price_tick] = level
        level[order.id] = order          # appended at the tail -> arrives last in FIFO
        self.orders[order.id] = order

    def _remove_if_empty(self, book: "SortedDict", tick: int) -> None:
        """Drop a price level from the book once its FIFO queue is empty."""
        if not book[tick]:
            del book[tick]

    # ---- matching ------------------------------------------------------------------

    def _crosses(self, taker_side: Side, limit_tick: int | None, best_opposite: int) -> bool:
        """
        Is a taker order marketable against the current best opposite price?

        A market order (limit_tick is None) always crosses if liquidity exists.
        A buy limit crosses when its price >= best ask; a sell limit when its
        price <= best bid.
        """
        if limit_tick is None:
            return True
        if taker_side == Side.BUY:
            return limit_tick >= best_opposite
        return limit_tick <= best_opposite

    def _match(self, taker: Order, limit_tick: int | None) -> list[Trade]:
        """
        Walk the opposite side, consuming resting orders in price-then-time
        order, until the taker is exhausted or no more marketable liquidity
        remains. Trades print at the resting *maker's* price (price improvement).
        """
        trades: list[Trade] = []
        opposite = self.asks if taker.side == Side.BUY else self.bids

        while taker.remaining > 0 and opposite:
            # Best opposite price: lowest ask for a buyer, highest bid for a seller.
            best_tick = opposite.peekitem(0)[0] if taker.side == Side.BUY \
                else opposite.peekitem(-1)[0]
            if not self._crosses(taker.side, limit_tick, best_tick):
                break

            level = opposite[best_tick]
            # FIFO: fill the oldest resting order at this level first.
            while taker.remaining > 0 and level:
                maker_id = next(iter(level))          # O(1) front of the queue
                maker = level[maker_id]
                qty = min(taker.remaining, maker.remaining)

                trades.append(Trade(
                    price_tick=best_tick,             # maker's price -> taker may improve
                    quantity=qty,
                    taker_side=taker.side,
                    maker_id=maker.id,
                    taker_id=taker.id,
                ))
                taker.remaining -= qty
                maker.remaining -= qty

                if maker.remaining == 0:
                    del level[maker_id]
                    del self.orders[maker_id]

            self._remove_if_empty(opposite, best_tick)

        return trades

    # ---- public API ----------------------------------------------------------------

    def submit_limit(self, side: Side, price: float, quantity: int) -> tuple[Order, list[Trade]]:
        """
        Submit a limit order. It first crosses any marketable liquidity, then
        rests its unfilled residual on the book at its own price.

        Returns the (possibly partially filled) Order and the list of Trades.
        """
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        tick = self.to_ticks(price)
        order = Order(id=next(self._ids), side=side, price_tick=tick,
                      quantity=quantity, remaining=quantity)
        trades = self._match(order, limit_tick=tick)
        if order.remaining > 0:
            self._rest(order)
        return order, trades

    def submit_market(self, side: Side, quantity: int) -> tuple[Order, list[Trade]]:
        """
        Submit a market order. It crosses until filled or the book is dry; any
        unfilled shortfall is simply discarded (a market order never rests).

        Returns the Order (inspect `remaining` for the shortfall) and Trades.
        """
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        order = Order(id=next(self._ids), side=side, price_tick=0,
                      quantity=quantity, remaining=quantity)
        trades = self._match(order, limit_tick=None)
        return order, trades

    def cancel(self, order_id: int) -> Order | None:
        """
        Cancel a resting order by id. Returns the removed Order, or None if the
        id is unknown (already filled or never existed).
        """
        order = self.orders.pop(order_id, None)
        if order is None:
            return None
        book = self._book_for(order.side)
        level = book.get(order.price_tick)
        if level is not None:
            level.pop(order_id, None)
            self._remove_if_empty(book, order.price_tick)
        return order

    # ---- depth snapshot (for the GUI / analysis) -----------------------------------

    def depth(self, side: Side, levels: int = 10) -> list[tuple[int, int]]:
        """
        Return up to `levels` (tick, total_quantity) pairs from best to worst
        for the given side. Best first: descending for bids, ascending for asks.
        """
        book = self._book_for(side)
        ticks = reversed(book.keys()) if side == Side.BUY else book.keys()
        out: list[tuple[int, int]] = []
        for tick in ticks:
            total = sum(o.remaining for o in book[tick].values())
            out.append((tick, total))
            if len(out) >= levels:
                break
        return out
