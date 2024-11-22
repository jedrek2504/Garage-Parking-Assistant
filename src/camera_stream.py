# src/camera_stream.py

from flask import Flask, Response
from shared_camera import SharedCamera
import cv2
import logging
import time

def run_flask_app(distances):
    # Configure logging for the Flask app to log to console
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] [Flask] %(message)s',
        handlers=[
            logging.StreamHandler()  # Log to console
        ]
    )

    logger = logging.getLogger('FlaskApp')

    app = Flask(__name__)

    # Get the shared camera instance
    picam2 = SharedCamera.get_instance()
    logger.info("Camera accessed by Flask app.")

    def gen_frames():
        try:
            while True:
                # Capture frame-by-frame
                frame = picam2.capture_array()

                # Convert color from RGB to BGR (OpenCV uses BGR)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                # Flip the frame vertically and horizontally (rotate 180 degrees)
                frame = cv2.flip(frame, -1)

                # Encode the frame in JPEG format with higher quality
                ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                if not ret:
                    logger.warning("Failed to encode frame.")
                    continue  # Skip the frame if encoding failed

                # Convert the frame to bytes and yield it
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

                # Sleep to control frame rate (approximate delay for 15 FPS)
                time.sleep(0.066)
        except GeneratorExit:
            # Handle generator exit when client disconnects
            logger.info("Client disconnected from video feed.")
        except Exception as e:
            logger.exception("Exception in gen_frames.")
        finally:
            pass  # Camera will be stopped in the main function

    @app.route('/video_feed')
    def video_feed():
        logger.info("Client connected to /video_feed.")
        return Response(gen_frames(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')

    try:
        app.run(host='0.0.0.0', port=5000)
    except Exception as e:
        logger.exception("Exception in Flask app.")
    finally:
        # Do not stop the camera here as it's shared
        logger.info("Flask app terminated.")
