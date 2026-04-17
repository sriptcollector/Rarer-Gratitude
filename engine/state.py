"""In-process shared state between the bot thread and the Flask dashboard."""
state: dict = {
    "symbols": [],
    "last_tick_ts": None,
    "last_tick_ms": None,
    "boot_error": None,
    "open_positions": 0,
    "total_trades_today": 0,
}
