"""Single-process entrypoint for Railway: runs the bot in a background
thread and serves the dashboard on $PORT."""
import os
import threading
import time
import logging

import config
import main as bot_main
from dashboard import app
from storage import db as dbm

log = logging.getLogger("entry")


def _run_bot():
    bot_main._supervised()


if __name__ == "__main__":
    os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
    dbm.init(config.DB_PATH).close()
    threading.Thread(target=_run_bot, daemon=True, name="bot").start()
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
