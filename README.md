# Limit Order Book Simulator

A price-time-priority **limit order book matching engine** in Python, with a
stochastic order-flow simulator, a live desktop GUI, and a quantitative
analytics layer for market-microstructure signals.

The matching core is pure — no GUI, no I/O, no global state — so it can be
reasoned about and unit-tested in isolation, while everything else (simulator,
analytics, GUI) is built as a layer on top of it.

## Features

- **Matching engine** (`order_book.py`) — price-time priority with bid/ask
  levels backed by sorted price maps and per-level FIFO queues, giving
  logarithmic-time inserts/cancels and constant-time order-id lookups. Prices
  are quantized to integer ticks to eliminate floating-point drift.
- **Order types** — market, limit, and marketable-limit orders, with
  maker-price improvement and partial fills.
- **Microstructure analytics** (`analytics.py`) — VWAP, realized volatility,
  and order-book imbalance (OBI), with trade-tape metrics vectorised in NumPy.
- **Market simulator** (`market_sim.py`) — a seeded stochastic order-flow
  generator that injects orders each tick (a toy model, not a calibrated
  market).
- **Live GUI** (`app.py`) — a `tkinter` view layer: price ladder, depth chart,
  trade tape, order entry, and run controls.
- **Tests** — unit tests over matching semantics plus randomized property
  testing enforcing share-conservation and no-crossed-book (`bid < ask`)
  invariants.

## Setup

```bash
pip install -r requirements.txt
```

`tkinter` ships with CPython on Windows/macOS; on Linux install `python3-tk`.

## Usage

```bash
python app.py              # launch the live GUI
python demo_analytics.py   # run the simulator and print VWAP / volatility / imbalance
python -m pytest           # run the test suite
```

### Using the engine directly

```python
from order_book import OrderBook, Side

book = OrderBook(tick_size=0.01)

# Rest passive liquidity
book.submit_limit(Side.BUY,  100.00, 10)
book.submit_limit(Side.SELL, 100.05, 10)

# An aggressive order crosses and generates trades
order, trades = book.submit_market(Side.BUY, 4)

print(book.best_bid(), book.best_ask(), book.spread())
```

## Project layout

| File | Role |
|------|------|
| `order_book.py` | Matching engine — pure, testable core |
| `analytics.py` | VWAP, realized volatility, order-book imbalance |
| `market_sim.py` | Seeded stochastic order-flow generator |
| `app.py` | `tkinter` GUI |
| `demo_analytics.py` | Runs the simulator and prints the analytics |
| `test_order_book.py`, `test_analytics.py` | Test suites |
