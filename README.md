# Limit Order Book Simulator

A price-time-priority **limit order book (LOB) matching engine** in Python, with
a stochastic order-flow simulator, a live exchange-style GUI, and a quantitative
analytics layer for market-microstructure signals.

The matching engine is a **pure module** — no GUI, no I/O, no global state — so
it can be reasoned about and reused anywhere. The simulator, analytics, and GUI
are all thin clients built on top of its public API.

## How it works

An order book keeps, for one instrument, two sorted sets of resting orders: the
**bids** (buy orders, best = highest price) and the **asks** (sell orders,
best = lowest price). An incoming order that can trade immediately is matched
against the resting book under **price-time priority**:

1. **Price priority** — the best price is filled first (a buyer takes the
   cheapest asks; a seller hits the highest bids).
2. **Time priority** — within a price level, the order that arrived first is
   filled first (FIFO).

Trades print at the resting (maker) order's price, so an aggressor can receive
**price improvement** relative to its own limit. Anything that can't trade
immediately **rests** in the book as passive liquidity.

## Design & complexity

Prices are quantized to an integer number of ticks internally, so price levels
are exact dictionary keys — no floating-point drift. With `L` = number of
distinct price levels:

| Operation | Structure | Complexity |
|-----------|-----------|------------|
| Best bid / best ask | `SortedDict` per side (keyed by tick) | `O(log L)` |
| Rest a new limit order | find/create level, append | `O(log L)` |
| Cancel by order id | `_orders` index + per-level `OrderedDict` | `O(log L)` |
| Match a marketable order | walk levels most-aggressive-first | `O(k + m log L)` |

Each price level stores its resting orders in an `OrderedDict` keyed by order
id, so insertion order *is* time priority (FIFO front is `next(iter(...))`)
while cancellation stays `O(1)` within the level. A global `_orders` index gives
`O(1)` order lookup.

## Analytics

`analytics.py` measures the market without changing how it matches, with
trade-tape metrics vectorised in NumPy:

- **VWAP** — volume-weighted average price; the standard execution benchmark.
- **Realized volatility** — standard deviation of trade-to-trade log returns; a
  model-free measure of how much the traded price is moving.
- **Order-book imbalance (OBI)** — `(bid_qty − ask_qty) / (bid_qty + ask_qty)`
  over the top levels, in `[−1, +1]`; resting-liquidity pressure.

## Market simulator

`market_sim.py` keeps the book alive with synthetic flow. A latent fair value
follows a drifting random walk; each tick fires three independent, Poisson-rated
streams — passive **limit orders** placed at exponential offsets from fair value,
aggressive **market orders** that cross the spread, and **cancellations** of
stale quotes. It is a deliberately *toy* microstructure model (seedable via
`SimConfig(seed=...)` for reproducibility), not a calibrated one, and uses only
the standard-library `random` module.

## Live GUI

`app.py` is a `tkinter` "depth of market" screen with a dark, terminal-style
theme: a color-coded **price ladder** (best bid/ask, spread, mid), a
cumulative-**depth chart**, a **time & sales tape**, live VWAP / volatility /
imbalance readouts, a **manual order-entry** panel (submit limit/market orders,
cancel your own resting orders), run controls (start/pause flow, speed,
aggressiveness, reset), and a built-in "how matching works" help window. The
real-time loop is driven by `root.after` — no blocking sleeps on the Tk thread.

## Setup

```bash
pip install -r requirements.txt
```

`tkinter` ships with CPython on Windows/macOS; on Linux install `python3-tk`.

## Usage

```bash
python app.py              # launch the live GUI
python demo_analytics.py   # run the simulator and print VWAP / volatility / imbalance
```

### Using the engine as a library

The matching engine stands alone — you can drive it directly without the GUI:

```python
from order_book import OrderBook, Side

book = OrderBook(tick_size=0.01)

# Rest passive liquidity on both sides
book.submit_limit(Side.BUY,  100.00, 10)
book.submit_limit(Side.SELL, 100.05, 10)

# An aggressive market buy crosses the spread and trades
order, trades = book.submit_market(Side.BUY, 4)

print(book.best_bid(), book.best_ask(), book.spread())  # -> 100.0 100.05 0.05
```

## Project layout

| File | Role |
|------|------|
| `order_book.py` | Matching engine — pure, self-contained core |
| `analytics.py` | VWAP, realized volatility, order-book imbalance |
| `market_sim.py` | Seeded stochastic order-flow generator |
| `app.py` | `tkinter` depth-of-market GUI |
| `demo_analytics.py` | Runs the simulator and prints the analytics |
| `requirements.txt` | Dependencies (`sortedcontainers`, `numpy`) |
