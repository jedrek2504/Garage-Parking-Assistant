from flask import Flask, Response
import cv2
import numpy as np
import os
import logging
from picamera2 import Picamera2

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console logging for real-time feedback
        logging.FileHandler('test_ai.log', mode='w')  # Log file
    ]
)
logger = logging.getLogger(__name__)

# Initialize camera using Picamera2
picam2 = Picamera2()
video_config = picam2.create_video_configuration(main={"size": (320, 240)})
picam2.configure(video_config)
picam2.start()
logger.info("Camera started.")

# Initialize background subtractor
background_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=25, detectShadows=True)

# Frame skipping configuration
process_every_n_frames = 5
frame_count = 0

# Function to classify objects based on size and shape
def classify_object(contour, frame_width, frame_height):
    x, y, w, h = cv2.boundingRect(contour)
    aspect_ratio = w / float(h)
    area = cv2.contourArea(contour)

    if area > 5000 and aspect_ratio > 1.5:  # Larger objects classified as cars
        return "car"
    elif area > 1000:  # Smaller objects classified as obstacles
        return "foreign object"
    return None

def generate_frames():
    global frame_count

    while True:
        try:
            # Increment frame count
            frame_count += 1

            # Capture frame
            frame = picam2.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            # Skip processing for non-relevant frames
            if frame_count % process_every_n_frames != 0:
                # Yield unprocessed frame as JPEG
                ret, buffer = cv2.imencode('.jpg', frame)
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                continue

            # Define Region of Interest (ROI)
            roi = frame[100:300, 50:400]  # Adjust ROI as per your garage layout

            # Background subtraction
            fg_mask = background_subtractor.apply(roi)

            # Noise removal
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)

            # Find contours
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            car_detected = False
            foreign_object_detected = False

            # Analyze contours
            for contour in contours:
                classification = classify_object(contour, frame.shape[1], frame.shape[0])
                if classification:
                    x, y, w, h = cv2.boundingRect(contour)
                    color = (0, 255, 0) if classification == "car" else (0, 0, 255)

                    # Draw rectangle and label
                    cv2.rectangle(frame, (x + 50, y + 100), (x + w + 50, y + h + 100), color, 2)
                    cv2.putText(frame, classification, (x + 50, y + 90),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

                    if classification == "car":
                        car_detected = True
                    elif classification == "foreign object":
                        foreign_object_detected = True

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
