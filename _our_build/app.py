"""
app.py — live tkinter GUI for the order book simulator.

Three views, refreshed on a timer:
  * Depth of Market (DOM) ladder — resting size at each price, bids vs asks.
  * Cumulative depth chart — the classic staircase of stacked liquidity.
  * Time & Sales tape — the most recent trades, coloured by aggressor side.

Controls let you play/pause the flow, change speed and aggressiveness, reset,
and submit your own limit/market orders. Manual marketable orders are collared
to a 10% band around the mid to guard against fat-finger fills.

Run:  python app.py
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from order_book import OrderBook, Side
from market_sim import MarketSimulator

PRICE_BAND = 0.10          # 10% fat-finger collar around the mid
TAPE_MAX = 200             # trades kept in the tape
LADDER_LEVELS = 12         # price levels shown per side

BID_COLOR = "#1b7f3b"
ASK_COLOR = "#b3261e"
BG = "#0f1114"
PANEL = "#171a1f"
FG = "#e6e6e6"
GRID = "#2a2f36"


class OrderBookApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Order Book Simulator — Quant Guild")
        self.configure(bg=BG)
        self.geometry("1040x680")

        self.book = OrderBook(tick_size=0.01)
        self.sim = MarketSimulator(self.book)
        self.sim.warmup(250)

        self.running = True
        self.interval_ms = 120
        self.tape: list = []

        self._build_style()
        self._build_layout()
        self._tick()

    # ---- styling -------------------------------------------------------------------

    def _build_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=PANEL, foreground=FG, fieldbackground=PANEL)
        style.configure("TFrame", background=PANEL)
        style.configure("TLabel", background=PANEL, foreground=FG)
        style.configure("TButton", background="#242a31", foreground=FG)
        style.configure("Header.TLabel", font=("Menlo", 12, "bold"))
        style.configure("Stat.TLabel", font=("Menlo", 14, "bold"))

    # ---- layout --------------------------------------------------------------------

    def _build_layout(self):
        top = ttk.Frame(self); top.pack(fill="x", padx=8, pady=6)
        self.stat_var = tk.StringVar()
        ttk.Label(top, textvariable=self.stat_var, style="Stat.TLabel").pack(side="left")

        self._build_controls(top)

        body = ttk.Frame(self); body.pack(fill="both", expand=True, padx=8, pady=6)

        # Left: DOM ladder.
        left = ttk.Frame(body); left.pack(side="left", fill="y")
        ttk.Label(left, text="Depth of Market", style="Header.TLabel").pack(anchor="w")
        self.ladder = ttk.Treeview(
            left, columns=("bid", "price", "ask"), show="headings", height=2 * LADDER_LEVELS
        )
        for col, w in (("bid", 90), ("price", 90), ("ask", 90)):
            self.ladder.heading(col, text=col.upper())
            self.ladder.column(col, width=w, anchor="center")
        self.ladder.tag_configure("bid", foreground=BID_COLOR)
        self.ladder.tag_configure("ask", foreground=ASK_COLOR)
        self.ladder.pack(fill="y", expand=False)

        # Middle: cumulative depth chart.
        mid = ttk.Frame(body); mid.pack(side="left", fill="both", expand=True, padx=8)
        ttk.Label(mid, text="Cumulative Depth", style="Header.TLabel").pack(anchor="w")
        self.canvas = tk.Canvas(mid, bg=BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # Right: time & sales tape.
        right = ttk.Frame(body); right.pack(side="left", fill="y")
        ttk.Label(right, text="Time & Sales", style="Header.TLabel").pack(anchor="w")
        self.tape_view = ttk.Treeview(
            right, columns=("price", "qty", "side"), show="headings", height=2 * LADDER_LEVELS
        )
        for col, w in (("price", 80), ("qty", 60), ("side", 60)):
            self.tape_view.heading(col, text=col.upper())
            self.tape_view.column(col, width=w, anchor="center")
        self.tape_view.tag_configure("BUY", foreground=BID_COLOR)
        self.tape_view.tag_configure("SELL", foreground=ASK_COLOR)
        self.tape_view.pack(fill="y")

    def _build_controls(self, parent):
        ctl = ttk.Frame(parent); ctl.pack(side="right")

        self.play_btn = ttk.Button(ctl, text="⏸ Pause", command=self._toggle)
        self.play_btn.grid(row=0, column=0, padx=3)
        ttk.Button(ctl, text="⟳ Reset", command=self._reset).grid(row=0, column=1, padx=3)

        ttk.Label(ctl, text="Speed").grid(row=0, column=2, padx=(12, 2))
        self.speed = tk.DoubleVar(value=self.interval_ms)
        ttk.Scale(ctl, from_=400, to=20, variable=self.speed, length=110,
                  command=self._set_speed).grid(row=0, column=3)

        ttk.Label(ctl, text="Aggressiveness").grid(row=0, column=4, padx=(12, 2))
        self.aggr = tk.DoubleVar(value=self.sim.aggressiveness)
        ttk.Scale(ctl, from_=0.0, to=1.0, variable=self.aggr, length=110,
                  command=self._set_aggr).grid(row=0, column=5)

        # Manual order entry.
        entry = ttk.Frame(parent); entry.pack(side="right", padx=12)
        ttk.Label(entry, text="Qty").grid(row=0, column=0)
        self.qty_var = tk.StringVar(value="10")
        ttk.Entry(entry, textvariable=self.qty_var, width=6).grid(row=0, column=1, padx=2)
        ttk.Label(entry, text="Px").grid(row=0, column=2)
        self.px_var = tk.StringVar(value="")
        ttk.Entry(entry, textvariable=self.px_var, width=8).grid(row=0, column=3, padx=2)
        ttk.Button(entry, text="Buy", command=lambda: self._manual(Side.BUY)).grid(row=0, column=4, padx=2)
        ttk.Button(entry, text="Sell", command=lambda: self._manual(Side.SELL)).grid(row=0, column=5, padx=2)

    # ---- control callbacks ---------------------------------------------------------

    def _toggle(self):
        self.running = not self.running
        self.play_btn.config(text="⏸ Pause" if self.running else "▶ Play")

    def _reset(self):
        self.book = OrderBook(tick_size=0.01)
        self.sim = MarketSimulator(self.book, aggressiveness=self.aggr.get())
        self.sim.warmup(250)
        self.tape.clear()

    def _set_speed(self, _):
        self.interval_ms = int(self.speed.get())

    def _set_aggr(self, _):
        self.sim.aggressiveness = float(self.aggr.get())

    def _manual(self, side: Side):
        try:
            qty = int(self.qty_var.get())
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid order", "Quantity must be a positive integer.")
            return

        px_text = self.px_var.get().strip()
        if px_text == "":
            # Market order.
            _, trades = self.book.submit_market(side, qty)
            self._record(trades)
            return

        try:
            price = float(px_text)
        except ValueError:
            messagebox.showerror("Invalid order", "Price must be a number (or blank for market).")
            return

        # Fat-finger collar: clamp marketable manual limits to a 10% band round the mid.
        mid = self.book.mid()
        if mid is not None:
            lo, hi = mid * (1 - PRICE_BAND), mid * (1 + PRICE_BAND)
            clamped = min(max(price, lo), hi)
            if clamped != price:
                messagebox.showwarning(
                    "Price banded",
                    f"Price {price:.2f} collared to {clamped:.2f} (±{int(PRICE_BAND*100)}% of mid).",
                )
                price = clamped

        _, trades = self.book.submit_limit(side, price, qty)
        self._record(trades)

    # ---- tape + rendering ----------------------------------------------------------

    def _record(self, trades):
        for t in trades:
            self.tape.append(t)
        if len(self.tape) > TAPE_MAX:
            self.tape = self.tape[-TAPE_MAX:]

    def _tick(self):
        if self.running:
            self._record(self.sim.step())
        self._render()
        self.after(self.interval_ms, self._tick)

    def _render(self):
        b = self.book
        bb, ba, mid = b.best_bid(), b.best_ask(), b.mid()
        spread = b.spread()
        self.stat_var.set(
            "  " + "   ".join([
                f"Bid {b.to_price(bb):.2f}" if bb is not None else "Bid —",
                f"Ask {b.to_price(ba):.2f}" if ba is not None else "Ask —",
                f"Mid {mid:.2f}" if mid is not None else "Mid —",
                f"Spr {spread}t" if spread is not None else "Spr —",
                f"Last {b.to_price(self.tape[-1].price_tick):.2f}" if self.tape else "Last —",
            ])
        )
        self._render_ladder()
        self._render_depth()
        self._render_tape()

    def _render_ladder(self):
        self.ladder.delete(*self.ladder.get_children())
        asks = self.book.depth(Side.SELL, LADDER_LEVELS)      # best (low) first
        bids = self.book.depth(Side.BUY, LADDER_LEVELS)       # best (high) first
        # Asks shown worst-at-top so the inside market meets in the middle.
        for tick, qty in reversed(asks):
            self.ladder.insert("", "end", values=("", f"{self.book.to_price(tick):.2f}", qty), tags=("ask",))
        for tick, qty in bids:
            self.ladder.insert("", "end", values=(qty, f"{self.book.to_price(tick):.2f}", ""), tags=("bid",))

    def _render_depth(self):
        c = self.canvas
        c.delete("all")
        w = c.winfo_width() or 400
        h = c.winfo_height() or 400
        bids = self.book.depth(Side.BUY, 40)
        asks = self.book.depth(Side.SELL, 40)
        if not bids and not asks:
            return

        # Cumulative sizes.
        def cumulate(levels):
            out, run = [], 0
            for tick, qty in levels:
                run += qty
                out.append((tick, run))
            return out

        cbids = cumulate(bids)
        casks = cumulate(asks)
        max_cum = max([q for _, q in cbids + casks] + [1])
        all_ticks = [t for t, _ in cbids + casks]
        lo, hi = min(all_ticks), max(all_ticks)
        span = max(hi - lo, 1)

        def x(tick):
            return (tick - lo) / span * (w - 20) + 10

        def y(cum):
            return h - 20 - (cum / max_cum) * (h - 40)

        # Zero baseline.
        c.create_line(10, h - 20, w - 10, h - 20, fill=GRID)

        def staircase(levels, color):
            pts = []
            for tick, cum in levels:
                pts.append((x(tick), y(cum)))
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                c.create_line(x0, y0, x1, y0, fill=color, width=2)
                c.create_line(x1, y0, x1, y1, fill=color, width=2)
            for xp, yp in pts:
                c.create_line(xp, h - 20, xp, yp, fill=color, width=1, stipple="gray25")

        staircase(sorted(cbids, key=lambda p: -p[0]), BID_COLOR)   # bids descend from mid
        staircase(sorted(casks, key=lambda p: p[0]), ASK_COLOR)    # asks ascend from mid

        mid = self.book.mid()
        if mid is not None:
            mx = x(self.book.to_ticks(mid))
            c.create_line(mx, 10, mx, h - 20, fill="#8a8f98", dash=(3, 3))

    def _render_tape(self):
        self.tape_view.delete(*self.tape_view.get_children())
        for t in reversed(self.tape[-2 * LADDER_LEVELS:]):
            self.tape_view.insert(
                "", "end",
                values=(f"{self.book.to_price(t.price_tick):.2f}", t.quantity, t.taker_side.value),
                tags=(t.taker_side.value,),
            )


if __name__ == "__main__":
    OrderBookApp().mainloop()
