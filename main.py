import sys
import os
import logging
import traceback
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "log.txt")

try:
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        encoding="utf-8",
    )
except PermissionError:
    LOG_FILE = os.path.join(os.path.expanduser("~"), "zpl_editor_log.txt")
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        encoding="utf-8",
    )

logger = logging.getLogger("ZPLEditor")


def handle_exception(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))


sys.excepthook = handle_exception

if __name__ == "__main__":
    logger.info("=== ZPL Visual Editor starting ===")
    try:
        from zpl_editor.app import run
        run()
    except Exception:
        logger.critical("Fatal error:\n%s", traceback.format_exc())
        print(f"HATA! Detaylar log.txt dosyasinda. ({datetime.now()})")
        sys.exit(1)
    finally:
        logger.info("=== ZPL Visual Editor closed ===")
