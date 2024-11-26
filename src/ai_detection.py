# src/ai_detection.py

import cv2
import threading
import logging
import time
from shared_camera import SharedCamera
import os

logger = logging.getLogger(__name__)

class AIModule:
    def __init__(self, config, callback):
        self.config = config
        self.callback = callback  # Callback to communicate with main loop
        self.background_frame_path = 'background_frame.jpg'
        self.background_frame = cv2.imread(self.background_frame_path)
        if self.background_frame is None:
            raise FileNotFoundError("Background frame not found.")
        self.frame_save_count = 0
        self.roi_top_left = (50, 10)
        self.roi_bottom_right = (575, 400)
        self.background_roi = self.background_frame[
            self.roi_top_left[1]:self.roi_bottom_right[1],
            self.roi_top_left[0]:self.roi_bottom_right[0],
        ]
        self.thread = None
        self.stop_event = threading.Event()

    def start(self):
        if self.thread and self.thread.is_alive():
            logger.warning("AI Module thread already running.")
        else:
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._run_detection, daemon=True)
            self.thread.start()
            logger.info("AI Module started.")

    def _run_detection(self):
        camera = SharedCamera.get_instance()
        
        if not self.stop_event.is_set():
            # Ensure LEDs are in default state before capturing frame
            time.sleep(0.1)  # Short delay to ensure LEDs are reset
            # Capture frame
            frame = camera.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            frame = cv2.flip(frame, -1)

            # Analyze frame
            obstacle_detected = self._process_frame(frame)
            self.callback(obstacle_detected)
        
        # AI module stops itself after one detection
        self.stop()

    def _process_frame(self, frame, frame_index=0):
        roi = frame[
            self.roi_top_left[1]:self.roi_bottom_right[1],
            self.roi_top_left[0]:self.roi_bottom_right[0],
        ]
        diff = cv2.absdiff(roi, self.background_roi)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, fg_mask = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY)  # Adjust threshold if needed
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=2)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_DILATE, kernel, iterations=1)

        # Find contours
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Draw contours on a copy of the ROI for visualization
        roi_with_contours = roi.copy()
        cv2.drawContours(roi_with_contours, contours, -1, (0, 255, 0), 2)

        # Save images for debugging
        debug_dir = 'debug_images'
        os.makedirs(debug_dir, exist_ok=True)
        frame_number = self.frame_save_count
        self.frame_save_count += 1

        cv2.imwrite(os.path.join(debug_dir, f'frame_{frame_number}.jpg'), frame)
        cv2.imwrite(os.path.join(debug_dir, f'roi_{frame_number}.jpg'), roi)
        cv2.imwrite(os.path.join(debug_dir, f'diff_{frame_number}.jpg'), diff)
        cv2.imwrite(os.path.join(debug_dir, f'fg_mask_{frame_number}.jpg'), fg_mask)
        cv2.imwrite(os.path.join(debug_dir, f'roi_contours_{frame_number}.jpg'), roi_with_contours)

        # Check for significant contours
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 1500:  # Adjust threshold to reduce false positives
                logger.debug(f"Detected object: area={area}")
                return True
        return False

    def stop(self):
        if self.thread and self.thread.is_alive():
            self.stop_event.set()
            if threading.current_thread() != self.thread:
                self.thread.join()
            logger.info("AI Module stopped.")
        else:
            logger.debug("AI Module is not running.")
