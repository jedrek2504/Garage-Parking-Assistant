# src/garage_parking_assistant/state_machine.py

import logging

logger = logging.getLogger(__name__)

class ParkingStateMachine:
    """
    Manages the process state: IDLE, PARKING, EXITING.
    Transitions triggered by detected car presence or user commands.
    """

    def __init__(self):
        self.process = None

    def start_parking(self):
        logger.info("Process: PARKING.")
        self.process = "PARKING"

    def start_exiting(self):
        logger.info("Process: EXITING.")
        self.process = "EXITING"

    def set_idle(self):
        logger.info("Process: IDLE.")
        self.process = None

    def is_parking(self):
        return self.process == "PARKING"

    def is_exiting(self):
        return self.process == "EXITING"

    def is_idle(self):
        return self.process is None
