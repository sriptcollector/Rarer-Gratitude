from .broker import PaperAccount


def summarize(acc: PaperAccount) -> dict:
    trades = acc.trades
    n = len(trades)
    if n == 0:
        return {
            "strategy": acc.strategy, "trades": 0, "win_rate": 0.0,
            "expectancy": 0.0, "profit_factor": 0.0, "avg_win": 0.0,
            "avg_loss": 0.0, "equity": acc.equity, "max_dd": acc.max_dd,
            "return_pct": 0.0,
        }
    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl <= 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    avg_win = gross_win / len(wins) if wins else 0.0
    avg_loss = gross_loss / len(losses) if losses else 0.0
    win_rate = len(wins) / n
    expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss
    pf = gross_win / gross_loss if gross_loss > 0 else float("inf")
    start_eq = acc.equity_curve[0][1] if acc.equity_curve else acc.equity
    return {
        "strategy": acc.strategy,
        "trades": n,
        "win_rate": round(win_rate, 4),
        "expectancy": round(expectancy, 4),
        "profit_factor": round(pf, 3) if pf != float("inf") else 999.0,
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
        "equity": round(acc.equity, 2),
        "max_dd": round(acc.max_dd, 4),
        "return_pct": round((acc.equity / start_eq - 1) * 100, 3) if start_eq else 0.0,
    }
