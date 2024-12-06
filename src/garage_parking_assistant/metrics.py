# src/garage_parking_assistant/metrics.py

import logging
import time

logger = logging.getLogger(__name__)

class Metrics:
    """
    Simple metrics container for logging system behavior.
    """

    def __init__(self):
        self.obstacle_detections = 0
        self.cycles = 0
        self.last_report_time = time.time()

    def increment_obstacle(self):
        self.obstacle_detections += 1

    def increment_cycle(self):
        self.cycles += 1

    def log_metrics_if_due(self):
        # Log metrics every 60 seconds
        if time.time() - self.last_report_time > 60:
            logger.info(f"Metrics Report: {self.cycles} cycles, {self.obstacle_detections} obstacles detected so far.")
            self.last_report_time = time.time()
