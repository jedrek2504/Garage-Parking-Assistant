# src/garage_parking_assistant/ai_detection.py

import cv2
import threading
import logging
import time
from shared_camera import SharedCamera
from exceptions import CameraError, GarageParkingAssistantError
from leds.led import set_led_segment_color, clear_leds  # Adjusted import path

logger = logging.getLogger(__name__)

class AIModule:
    def __init__(self, config, callback):
        self.config = config
        self.callback = callback  # Callback to communicate with main loop
        self.background_frame_path = self.config.BACKGROUND_FRAME_PATH
        self.background_frame = self._load_background_frame()
        self.frame_save_count = 0
        self.roi_top_left = (110, 60)
        self.roi_bottom_right = (550, 470)
        self.background_roi = self.background_frame[
            self.roi_top_left[1]:self.roi_bottom_right[1],
            self.roi_top_left[0]:self.roi_bottom_right[0],
        ]
        self.thread = None
        self.stop_event = threading.Event()
        self.area_threshold = 1500  # Area threshold for detecting objects

    def _load_background_frame(self):
        """
        Loads the background frame. If it doesn't exist, captures it.
        
        Returns:
            ndarray: The loaded background frame.
        
        Raises:
            CameraError: If unable to load or capture the background frame.
        """
        background_frame = cv2.imread(self.background_frame_path)
        if background_frame is None:
            logger.error(f"Background frame not found at {self.background_frame_path}. Initiating capture.")
            self._capture_background_frame()
            background_frame = cv2.imread(self.background_frame_path)
            if background_frame is None:
                logger.error(f"Failed to capture background frame at {self.background_frame_path}.")
                raise CameraError("AIModule", "Background frame not found and capture failed.")
        logger.info(f"Background frame loaded from {self.background_frame_path}.")
        return background_frame

    def _capture_background_frame(self):
        """
        Captures the background frame by turning all LEDs green,
        capturing the image, and then clearing the LEDs.
        
        Raises:
            CameraError: If unable to capture the background frame.
        """
        try:
            logger.info("Capturing background frame.")
            # Turn all LED segments to green
            for segment in ['left', 'front', 'right']:
                set_led_segment_color(segment, 0, 255, 0, brightness=20, update_immediately=True)

            # Allow time for the LEDs to turn on
            logger.info("LED segments turned green with 20/255 brightness. Waiting for 2 seconds before capturing background...")
            time.sleep(2)

            # Capture background frame
            camera = SharedCamera.get_instance()
            frame = camera.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            frame = cv2.flip(frame, -1)
            cv2.imwrite(self.background_frame_path, frame)
            logger.info(f"Background frame captured and saved as {self.background_frame_path}.")

            # Keep the LEDs on for additional time if needed
            time.sleep(5)

        except Exception as e:
            logger.exception("Failed to capture background frame.")
            raise CameraError("AIModule", "Failed to capture background frame.") from e

        finally:
            # Clear all LEDs
            clear_leds()
            logger.info("All LEDs cleared after background capture.")

    def start(self):
        try:
            if self.thread and self.thread.is_alive():
                logger.warning("AI Module thread already running.")
            else:
                self.stop_event.clear()
                self.thread = threading.Thread(target=self._run_detection, daemon=True)
                self.thread.start()
                logger.info("AI Module started.")
        except Exception as e:
            logger.exception("Failed to start AI Module.")
            raise GarageParkingAssistantError("Failed to start AI Module") from e

    def _majority_vote(self, detection_results):
        positive_detections = sum(detection_results)
        if positive_detections > len(detection_results) / 2:
            logger.debug(f"Object detected in majority of frames ({positive_detections}/{len(detection_results)}).")
            return True
        else:
            logger.debug(f"No object detected in majority of frames ({positive_detections}/{len(detection_results)}).")
            return False

    def _run_detection(self):
        try:
            camera = SharedCamera.get_instance()
            frame_count = 3  # Number of frames to process
            detection_results = []

            if not self.stop_event.is_set():
                # Capture and process frames in separate threads
                threads = []
                for i in range(frame_count):
                    thread = threading.Thread(target=self._capture_and_process_frame, args=(camera, detection_results, i))
                    threads.append(thread)
                    thread.start()
                    time.sleep(0.1)  # Stagger the start times slightly

                for thread in threads:
                    thread.join()

                # Determine final result based on majority vote
                object_present = self._majority_vote(detection_results)
                self.callback(object_present)
        except CameraError as e:
            logger.error(f"Camera error during AI detection: {e}")
            self.callback(False)
        except Exception as e:
            logger.exception("Unexpected error in AI detection module.")
            self.callback(False)
        finally:
            # AI module stops itself after one detection
            self.stop()

    def _capture_and_process_frame(self, camera, detection_results, frame_index):
        try:
            frame = camera.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            frame = cv2.flip(frame, -1)
            obstacle_detected = self._process_frame(frame)
            detection_results.append(obstacle_detected)
        except CameraError as e:
            logger.error(f"Camera error during frame capture: {e}")
            detection_results.append(False)
        except Exception as e:
            logger.exception("Unexpected error during frame capture and processing.")
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
                area = cv2.contourArea(cnt)
                if area > self.area_threshold:
                    logger.debug(f"Detected object: area={area}")
                    return True
            return False
        except Exception as e:
            logger.exception("Failed to process frame for obstacle detection.")
            return False

    def stop(self):
        try:
            if self.thread and self.thread.is_alive():
                self.stop_event.set()
                if threading.current_thread() != self.thread:
                    self.thread.join()
                logger.info("AI Module stopped.")
            else:
                logger.debug("AI Module is not running.")
        except Exception as e:
            logger.exception("Failed to stop AI Module.")
            raise GarageParkingAssistantError("Failed to stop AI Module") from e
