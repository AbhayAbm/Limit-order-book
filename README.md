# Limit Order Book Simulator

A price-time-priority **limit order book matching engine** in Python, with a
stochastic order-flow simulator, a live desktop GUI, and a quantitative
analytics layer.

The matching core is pure — no GUI, no I/O, no global state — so it can be
reasoned about and unit-tested in isolation.

## Highlights

- **Matching engine** (`order_book.py`) — price-time priority with bid/ask
  levels backed by sorted price maps and per-level FIFO queues, giving
  logarithmic-time inserts/cancels and constant-time ID lookups. Prices are
  tick-quantized to integer ticks to eliminate floating-point drift.
- **Order types** — market, limit, and marketable-limit orders, with
  maker-price improvement and partial fills.
- **Analytics** (`analytics.py`) — VWAP, realized volatility, and order-book
  imbalance (OBI), with tape metrics vectorised in NumPy.
- **Simulator** (`market_sim.py`) — a stochastic order-flow generator that
  injects orders each tick (a toy model, not a calibrated market).
- **GUI** (`app.py`) — a `tkinter` view layer: price ladder, depth chart, trade
  tape, order entry, and controls.
- **Tests** (`test_order_book.py`, `test_analytics.py`) — unit tests over
  matching semantics plus randomized property testing that enforces
  share-conservation and no-crossed-book (`bid < ask`) invariants.

## Setup

```bash
pip install -r requirements.txt
```

`tkinter` ships with CPython on Windows/macOS; on Linux install `python3-tk`.

## Usage

```bash
python app.py              # launch the live GUI
python -m pytest           # run the test suite
python demo_analytics.py   # print analytics over a simulated tape
```

## Layout

| File | Role |
|------|------|
| `order_book.py` | Matching engine (pure, testable) |
| `analytics.py` | VWAP / realized volatility / order-book imbalance |
| `market_sim.py` | Stochastic order-flow generator |
| `app.py` | `tkinter` GUI |
| `test_order_book.py`, `test_analytics.py` | Test suites |
