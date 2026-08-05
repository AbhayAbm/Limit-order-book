"""
analytics.py -- quantitative signals over the order book and trade tape.

This is the *quant* layer on top of the pure matching engine in
:mod:`order_book`. It does not change how orders match; it only *measures* the
market, with three signals:

  * **VWAP** and **realized volatility** -- computed from the executed trade
    tape; they describe what *has* traded (an execution benchmark and a
    model-free risk measure).
  * **Order-book imbalance (OBI)** -- computed from the *live* resting book; a
    standard microstructure measure of which side holds more resting liquidity.

Tape metrics are vectorised with NumPy -- the "vectorised analysis of the trade
tape" the project's requirements file anticipates.
"""

from __future__ import annotations

import numpy as np

from order_book import OrderBook, Side, Trade


def _price_size_arrays(tape: list[Trade]) -> tuple[np.ndarray, np.ndarray]:
    """Extract prices and sizes from a trade tape as parallel NumPy arrays."""
    if not tape:
        return np.empty(0), np.empty(0)
    prices = np.fromiter((t.price for t in tape), dtype=float, count=len(tape))
    sizes = np.fromiter((t.size for t in tape), dtype=float, count=len(tape))
    return prices, sizes


def vwap(tape: list[Trade]) -> float | None:
    """Volume-Weighted Average Price.

    The average execution price weighted by trade size -- the standard
    benchmark for execution quality (did you trade better or worse than the
    volume-weighted market?).  VWAP = sum(price_i * size_i) / sum(size_i).
    Returns None for an empty tape.
    """
    prices, sizes = _price_size_arrays(tape)
    if sizes.sum() == 0:
        return None
    return float((prices * sizes).sum() / sizes.sum())


def realized_volatility(tape: list[Trade]) -> float | None:
    """Realized volatility of trade-to-trade *log returns*.

    A model-free measure of how much the traded price is moving: the standard
    deviation of consecutive log price changes. Higher => choppier market.
    Returns None if there are fewer than two trades.
    """
    prices, _ = _price_size_arrays(tape)
    if prices.size < 2:
        return None
    log_returns = np.diff(np.log(prices))
    return float(np.std(log_returns))


def order_book_imbalance(book: OrderBook, levels: int = 5) -> float | None:
    """Order-Book Imbalance (OBI) over the top ``levels`` price levels.

        OBI = (bid_qty - ask_qty) / (bid_qty + ask_qty)   in [-1, +1]

    A standard microstructure measure of resting liquidity pressure: OBI -> +1
    means the bid side is much deeper than the ask side (buy-side pressure),
    OBI -> -1 means the opposite, and 0 is a balanced book. Returns None if the
    book is one-sided/empty.
    """
    bid_qty = sum(q for _, q in book.depth(Side.BUY, levels))
    ask_qty = sum(q for _, q in book.depth(Side.SELL, levels))
    total = bid_qty + ask_qty
    if total == 0:
        return None
    return (bid_qty - ask_qty) / total


__all__ = ["vwap", "realized_volatility", "order_book_imbalance"]
