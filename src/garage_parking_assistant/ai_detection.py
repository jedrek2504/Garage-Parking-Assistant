# src/garage_parking_assistant/ai_detection.py

import cv2
import threading
import logging
import time
from shared_camera import SharedCamera
from exceptions import CameraError, GarageParkingAssistantError
from leds.led import set_led_segment_color, clear_leds

logger = logging.getLogger(__name__)

class AIModule:
    def __init__(self, config, callback):
        """
        Initialize AI Module with configuration and callback.
        Loads background frame and sets ROI.
        """
        self.config = config
        self.callback = callback
        self.background_frame_path = self.config.BACKGROUND_FRAME_PATH
        self.background_frame = self._load_background_frame()
        self.roi_top_left = (110, 60)
        self.roi_bottom_right = (550, 470)
        self.background_roi = self.background_frame[
            self.roi_top_left[1]:self.roi_bottom_right[1],
            self.roi_top_left[0]:self.roi_bottom_right[0],
        ]
        self.thread = None
        self.stop_event = threading.Event()
        self.area_threshold = 1500  # Minimum area to detect an object
        self._running = False

    def _load_background_frame(self):
        """
        Load or capture the background frame.
        """
        background_frame = cv2.imread(self.background_frame_path)
        if background_frame is None:
            logger.error(f"Background frame not found at {self.background_frame_path}. Capturing...")
            self._capture_background_frame()
            background_frame = cv2.imread(self.background_frame_path)
            if background_frame is None:
                logger.error("Failed to capture background frame.")
                raise CameraError("AIModule", "Background frame capture failed.")
        logger.info("Background frame loaded.")
        return background_frame

    def _capture_background_frame(self):
        """
        Capture the background frame with LEDs green.
        """
        try:
            logger.info("Capturing background frame.")
            # Set LEDs to green
            for segment in ['left', 'front', 'right']:
                set_led_segment_color(segment, 0, 255, 0, brightness=20, update_immediately=True)
            logger.info("LEDs set to green. Waiting before capture...")
            time.sleep(2)

            # Capture and save frame
            camera = SharedCamera.get_instance()
            frame = camera.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            frame = cv2.flip(frame, -1)
            cv2.imwrite(self.background_frame_path, frame)
            logger.info("Background frame captured and saved.")
            time.sleep(5)  # Optional stabilization time
        except Exception as e:
            logger.exception("Failed to capture background frame.")
            raise CameraError("AIModule", "Background frame capture failed.") from e
        finally:
            clear_leds()
            logger.info("LEDs cleared after capture.")

    def start(self):
        """
        Start AI detection in a separate thread.
        """
        try:
            if self.thread and self.thread.is_alive():
                logger.warning("AI Module thread already running.")
            else:
                self.stop_event.clear()
                self._running = True
                self.thread = threading.Thread(target=self._run_detection, daemon=True)
                self.thread.start()
                logger.info("AI Module started.")
        except Exception as e:
            logger.exception("Failed to start AI Module.")
            raise GarageParkingAssistantError("Failed to start AI Module") from e

    def _majority_vote(self, detection_results):
        """
        Determine detection based on majority vote.
        """
        positive = sum(detection_results)
        return positive > len(detection_results) / 2

    def _run_detection(self):
        """
        Capture and process multiple frames to detect obstacles.
        """
        try:
            camera = SharedCamera.get_instance()
            frame_count = 3  # Number of frames
            detection_results = []

            if not self.stop_event.is_set():
                threads = []
                for i in range(frame_count):
                    thread = threading.Thread(target=self._capture_and_process_frame, args=(camera, detection_results))
                    threads.append(thread)
                    thread.start()
                    time.sleep(0.1)  # Slight stagger

                for thread in threads:
                    thread.join()

                object_present = self._majority_vote(detection_results)
                self.callback(object_present)
        except CameraError as e:
            logger.error(f"Camera error: {e}")
            self.callback(False)
        except Exception as e:
            logger.exception("Unexpected error in AI detection.")
            self.callback(False)
        finally:
            pass

    def _capture_and_process_frame(self, camera, detection_results):
        """
        Capture a frame and process it for obstacle detection.
        """
        try:
            frame = camera.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            frame = cv2.flip(frame, -1)
            detected = self._process_frame(frame)
            detection_results.append(detected)
        except CameraError as e:
            logger.error(f"Camera error during frame capture: {e}")
            detection_results.append(False)
        except Exception as e:
            logger.exception("Error during frame capture and processing.")
            detection_results.append(False)

    def _process_frame(self, frame):
        """
        Processes a single frame to detect obstacles.

        Args:
            frame (ndarray): The image frame to process.

        Returns:
            bool: True if an obstacle is detected, False otherwise.
        """
        try:
            # Extract the region of interest (ROI)
            roi = frame[self.roi_top_left[1]:self.roi_bottom_right[1],
                        self.roi_top_left[0]:self.roi_bottom_right[0]]

            # Compute the absolute difference between the current ROI and the background
            diff = cv2.absdiff(roi, self.background_roi)

            # Convert to grayscale and apply thresholding
            gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            _, fg_mask = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY)

            # Perform morphological operations to reduce noise
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=2)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_DILATE, kernel, iterations=1)

            # Find contours in the foreground mask
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Check for significant contours indicating an obstacle
            for cnt in contours:
                if cv2.contourArea(cnt) > self.area_threshold:
                    logger.debug(f"Object detected: area={cv2.contourArea(cnt)}")
                    return True
            return False
        except Exception as e:
            logger.exception("Failed to process frame.")
            return False

    def stop(self):
        """
        Stop the AI detection thread.
        """
        try:
            if self._running:  # Only stop if currently running
                self._running = False
                if self.thread and self.thread.is_alive():
                    self.stop_event.set()
                    if threading.current_thread() != self.thread:
                        self.thread.join()
                logger.info("AI Module stopped.")
            else:
                logger.debug("AI Module stop requested but it's not running.")
        except Exception as e:
            logger.exception("Failed to stop AI Module.")
            raise GarageParkingAssistantError("Failed to stop AI Module") from e
