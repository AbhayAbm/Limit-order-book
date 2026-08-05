"""
demo_analytics.py -- run the simulator and print the three quant signals.

Drives the market simulator for a while, accumulating the trade tape, then
reports VWAP and realized volatility over the tape plus the live order-book
imbalance. A quick sanity check that the analytics work end-to-end on real
simulated flow.

    python demo_analytics.py
"""

from order_book import OrderBook
from market_sim import MarketSimulator, SimConfig
from analytics import vwap, realized_volatility, order_book_imbalance

STEPS = 5_000


def main() -> None:
    book = OrderBook(tick_size=0.01)
    sim = MarketSimulator(book, SimConfig(seed=7))

    tape = []
    for _ in range(STEPS):
        tape += sim.step()

    print(f"Simulated {STEPS:,} steps, {len(tape):,} trades executed\n")
    print(f"VWAP                 : {vwap(tape):.4f}")
    print(f"Realized volatility  : {realized_volatility(tape):.6f}")
    print(f"Order-book imbalance : {order_book_imbalance(book):+.3f}")
    print(f"Live mid / spread    : {book.mid():.2f} / {book.spread()} ticks")


if __name__ == "__main__":
    main()
