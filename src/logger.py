import logging
import queue
from pathlib import Path
from datetime import datetime


class QueueHandler(logging.Handler):
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))


def setup_logger(log_queue: queue.Queue) -> logging.Logger:
    Path("logs").mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(f"logs/qac_{timestamp}.log")

    logger = logging.getLogger(f"qac_{timestamp}")
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    queue_handler = QueueHandler(log_queue)
    queue_handler.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(file_handler)
    logger.addHandler(queue_handler)
    return logger
