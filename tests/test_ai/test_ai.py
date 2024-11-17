from flask import Flask, Response
import cv2
import numpy as np
import os
import logging
from picamera2 import Picamera2
import time
from collections import defaultdict

# Dictionary to track persistent objects
detected_objects = defaultdict(lambda: {"bbox": None, "type": None, "last_seen": 0})
object_timeout = 5  # seconds

# Reference frame for stationary object detection
reference_frame = None
update_reference_interval = 100  # Update baseline every N frames
frame_counter = 0

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_ai.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

# Initialize camera using Picamera2
picam2 = Picamera2()
video_config = picam2.create_video_configuration(main={"size": (640, 480)}, controls={"FrameRate": 15})
picam2.configure(video_config)
picam2.start()
logger.info("Camera started.")

# Initialize background subtractor
background_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=25, detectShadows=True)

# ROI coordinates
roi_top_left = (50, 10)
roi_bottom_right = (575, 400)

# Updated function to classify objects with improved filtering
def classify_object(contour, frame_width, frame_height):
    x, y, w, h = cv2.boundingRect(contour)
    aspect_ratio = w / float(h)
    area = cv2.contourArea(contour)
    hull = cv2.convexHull(contour)
    hull_area = cv2.contourArea(hull)
    solidity = float(area) / hull_area if hull_area > 0 else 0

    # Exclude contours spanning the entire ROI
    if w > 0.9 * frame_width or h > 0.9 * frame_height:
        logger.info(f"Skipping contour: spans ROI (w={w}, h={h})")
        return None

    # Updated thresholds to filter out false positives
    if area > 15000 and 1.5 < aspect_ratio < 3.0 and solidity > 0.8:  # Large, compact contours are cars
        return "car"
    elif 1000 < area <= 15000 and solidity > 0.5:  # Smaller, compact contours are foreign objects
        return "foreign object"
    return None  # Ignore small or irregular contours


def generate_frames():
    global reference_frame, frame_counter

    while True:
        try:
            # Capture frame
            frame = picam2.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            # Flip frame upside down
            frame = cv2.flip(frame, 0)

            # Extract ROI
            roi = frame[roi_top_left[1]:roi_bottom_right[1], roi_top_left[0]:roi_bottom_right[0]]

            # Enhance ROI
            roi = cv2.convertScaleAbs(roi, alpha=1.5, beta=50)

            # Background subtraction for moving objects
            fg_mask = background_subtractor.apply(roi)

            # Noise removal
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)

            # Contour detection on foreground mask
            contours_fg, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Contour detection for stationary objects (frame differencing)
            if reference_frame is not None:
                frame_diff = cv2.absdiff(reference_frame, cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY))
                _, diff_thresh = cv2.threshold(frame_diff, 50, 255, cv2.THRESH_BINARY)
                contours_diff, _ = cv2.findContours(diff_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            else:
                contours_diff = []  # Ensure it's an empty list

            # Update reference frame periodically
            if frame_counter % update_reference_interval == 0:
                reference_frame = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

            # Increment frame counter
            frame_counter += 1

            car_detected = False
            foreign_object_detected = False

            # Combine contours from both methods (ensure both are lists)
            all_contours = list(contours_fg) + list(contours_diff)

            for contour in all_contours:
                classification = classify_object(contour, roi.shape[1], roi.shape[0])
                if classification:
                    x, y, w, h = cv2.boundingRect(contour)
                    color = (0, 255, 0) if classification == "car" else (0, 0, 255)

                    # Update persistent object dictionary
                    detected_objects[id(contour)] = {
                        "bbox": (x, y, w, h),
                        "type": classification,
                        "last_seen": time.time(),
                    }

                    # Draw rectangle and label
                    cv2.rectangle(frame, (x + roi_top_left[0], y + roi_top_left[1]),
                                  (x + w + roi_top_left[0], y + h + roi_top_left[1]), color, 2)
                    cv2.putText(frame, classification, (x + roi_top_left[0], y + roi_top_left[1] - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

                    if classification == "car":
                        car_detected = True
                    elif classification == "foreign object":
                        foreign_object_detected = True

            # Remove stale objects
            current_time = time.time()
            for obj_id, obj_data in list(detected_objects.items()):
                if current_time - obj_data["last_seen"] > object_timeout:
                    del detected_objects[obj_id]

            # Draw persistent objects
            for obj_data in detected_objects.values():
                x, y, w, h = obj_data["bbox"]
                classification = obj_data["type"]
                color = (0, 255, 0) if classification == "car" else (0, 0, 255)

                cv2.rectangle(frame, (x + roi_top_left[0], y + roi_top_left[1]),
                              (x + w + roi_top_left[0], y + h + roi_top_left[1]), color, 2)
                cv2.putText(frame, classification, (x + roi_top_left[0], y + roi_top_left[1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            # Log detections
            if car_detected:
                logger.info("Car detected.")
            if foreign_object_detected:
                logger.info("Foreign object detected.")
            if car_detected and foreign_object_detected:
                logger.info("Car and foreign object detected.")

            # Encode frame to JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()

            # Yield processed frame in byte format
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        except Exception as e:
            logger.exception("Exception in generate_frames.")
            break





@app.route('/video_feed')
def video_feed():
    logger.info("Client connected to /video_feed.")
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000)
    except Exception as e:
        logger.exception("Exception in Flask app.")
    finally:
        picam2.stop()
        logger.info("Camera stopped.")
