# ai_module.py

import threading
import time
import logging

logger = logging.getLogger(__name__)

class AIModule:
    def __init__(self, config, detection_callback):
        self.config = config
        self.detection_callback = detection_callback
        self.ai_thread = None
        self.running = False

    # jesli zaczyna sie proces parkowania (podniesiona wiata garazowa) rozpoczynamy analize ai na osobnym watku
    def start(self):
        if not self.running:
            self.running = True
            self.ai_thread = threading.Thread(target=self.ai_analysis)
            self.ai_thread.start()
            logger.info("AI analysis started.")
        else:
            logger.debug("AI analysis already running.")

    def stop(self):
        if self.running:
            self.running = False
            if self.ai_thread:
                self.ai_thread.join()
            logger.info("AI analysis stopped.")

    # podczas trwania analizy co okreslony czas  - tutaj jedna sekunda bedzie pobierana ramka z garazu i poddawana analizie
    def ai_analysis(self):
        while self.running:
            # Placeholder for AI analysis logic
            object_detected = self.mock_ai_detection()
            self.detection_callback(object_detected)
            time.sleep(1)

    # w zaleznosci od wyniku analizy zwracamy odpowiednia wartosc true/false
    def mock_ai_detection(self):
        # Simulate AI detection result
        return True

# jesli true (obiekt w garazu wykryty) -> sygnalizujemy alaramem(mrugające ledy)
# jesli false (brak obiektu w garazu) -> system dziala jak dotychczas.