# ai_detection.py

import cv2
import threading
import logging
import time
from shared_camera import SharedCamera

logger = logging.getLogger(__name__)

class AIDetection:
    def __init__(self, background_frame_path, led_manager, stop_event):
        self.background_frame = cv2.imread(background_frame_path)
        if self.background_frame is None:
            raise FileNotFoundError("Background frame not found.")
        
        self.led_manager = led_manager
        self.stop_event = stop_event
        self.roi_top_left = (50, 10)
        self.roi_bottom_right = (575, 400)
        self.background_roi = self.background_frame[
            self.roi_top_left[1]:self.roi_bottom_right[1],
            self.roi_top_left[0]:self.roi_bottom_right[0],
        ]
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive():
            logger.warning("AI Detection thread already running.")
        else:
            self.thread = threading.Thread(target=self._run_detection, daemon=True)
            self.thread.start()

    def _run_detection(self):
        camera = SharedCamera.get_instance()
        
        while not self.stop_event.is_set():
            # Capture frame
            frame = camera.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            frame = cv2.flip(frame, -1)

            # Analyze frame
            obstacle_detected = self._process_frame(frame)
            if obstacle_detected:
                logger.info("Obstacle detected. Starting LED blinking.")
                self.led_manager.start_blinking()
                
                # Blink LEDs for 10 seconds
                start_time = time.time()
                while time.time() - start_time < 10:
                    if self.stop_event.is_set():
                        return
                    time.sleep(0.1)

                self.led_manager.stop_blinking()
                logger.info("Reset LEDs for background correction.")

                # Wait briefly to reset LEDs
                time.sleep(1)
            else:
                logger.info("No obstacle detected. Stopping AI detection.")
                break

    def _process_frame(self, frame):
        roi = frame[
            self.roi_top_left[1]:self.roi_bottom_right[1],
            self.roi_top_left[0]:self.roi_bottom_right[0],
        ]
        diff = cv2.absdiff(roi, self.background_roi)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, fg_mask = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=2)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_DILATE, kernel, iterations=1)

        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 500:
                return True
        return False

    def stop(self):
        if self.thread and self.thread.is_alive():
            self.stop_event.set()
            self.thread.join()
        logger.info("AI Detection stopped.")
