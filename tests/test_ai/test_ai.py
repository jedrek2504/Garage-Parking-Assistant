# tests/test_ai/test_ai.py

from flask import Flask, Response
import cv2
import threading
import time
import numpy as np
import os
import sys
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

# Get the directory of the current script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Construct full paths to the model files
cfg_path = os.path.join(script_dir, 'yolov4-tiny.cfg')
weights_path = os.path.join(script_dir, 'yolov4-tiny.weights')
names_path = os.path.join(script_dir, 'coco.names')

# Check if files exist
for path in [cfg_path, weights_path, names_path]:
    if not os.path.isfile(path):
        logger.error(f"Error: File {path} not found.")
        sys.exit(1)

# Load YOLOv4-Tiny model
net = cv2.dnn.readNetFromDarknet(cfg_path, weights_path)
net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

# Load class labels
with open(names_path, 'r') as f:
    all_classes = [line.strip() for line in f.readlines()]

# Define simplified classes
classes = ['car', 'foreign object']

# Get output layer names using the correct method
output_layers = net.getUnconnectedOutLayersNames()

# Initialize camera using Picamera2
picam2 = Picamera2()
video_config = picam2.create_video_configuration(main={"size": (320, 240)})
picam2.configure(video_config)
picam2.start()
logger.info("Camera started.")

def generate_frames():
    while True:
        try:
            # Capture frame
            frame = picam2.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            # Perform object detection
            blob = cv2.dnn.blobFromImage(frame, 1/255.0, (416, 416), swapRB=True, crop=False)
            net.setInput(blob)
            outputs = net.forward(output_layers)

            # Initialize detection flags
            car_detected = False
            foreign_object_detected = False

            # Initialize lists
            class_ids = []
            confidences = []
            boxes = []

            # Process detections
            for output in outputs:
                for detection in output:
                    scores = detection[5:]
                    class_id = np.argmax(scores)
                    confidence = scores[class_id]

                    if confidence > 0.5:
                        # Map classes
                        if all_classes[class_id] == 'car':
                            mapped_class_id = 0  # Index for 'car'
                            car_detected = True
                        else:
                            mapped_class_id = 1  # Index for 'foreign object'
                            foreign_object_detected = True

                        # Object detected
                        center_x = int(detection[0] * frame.shape[1])
                        center_y = int(detection[1] * frame.shape[0])
                        width = int(detection[2] * frame.shape[1])
                        height = int(detection[3] * frame.shape[0])

                        # Rectangle coordinates
                        x = int(center_x - width / 2)
                        y = int(center_y - height / 2)

                        boxes.append([x, y, width, height])
                        confidences.append(float(confidence))
                        class_ids.append(mapped_class_id)

            # Apply Non-Max Suppression
            indexes = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)

            font = cv2.FONT_HERSHEY_SIMPLEX

            if len(indexes) > 0:
                for i in indexes.flatten():
                    x, y, w, h = boxes[i]
                    label = str(classes[class_ids[i]])
                    confidence = str(round(confidences[i], 2))
                    if class_ids[i] == 0:
                        color = (0, 255, 0)  # Green for car
                    else:
                        color = (0, 0, 255)  # Red for foreign object
                    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                    cv2.putText(frame, label + " " + confidence, (x, y - 10), font, 0.5, color, 1)

            # Encode frame to JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()

            # Yield frame in byte format
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

            # Check for both car and foreign object detection
            if car_detected and foreign_object_detected:
                logger.info("Car and foreign object detected.")
                # Implement any additional logic or callbacks here

        except GeneratorExit:
            # Handle generator exit when client disconnects
            logger.info("Client disconnected from video feed.")
            break
        except Exception as e:
            logger.exception("Exception in gen_frames.")
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
