# camera_stream.py

from flask import Flask, Response
from picamera2 import Picamera2
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

    # Initialize Picamera2 outside the generator function
    picam2 = Picamera2()
    video_config = picam2.create_video_configuration(
        main={"size": (320, 240)},
        controls={"FrameDurationLimits": (66666, 66666)}  # Set to ~15 FPS
    )
    picam2.configure(video_config)
    picam2.start()
    logger.info("Camera started.")

    def gen_frames():
        try:
            while True:
                # Capture frame-by-frame
                frame = picam2.capture_array()

                # Convert color from RGB to BGR (OpenCV uses BGR)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                # Flip the frame vertically and horizontally (rotate 180 degrees)
                frame = cv2.flip(frame, -1)

                # Overlay sensor values onto the frame
                font = cv2.FONT_HERSHEY_PLAIN
                font_scale = 0.5
                color = (0, 255, 0)
                thickness = 1
                line_type = cv2.LINE_AA

                # Acquire sensor readings with thread safety
                with distances['lock']:
                    distance_front = distances.get('front')
                    distance_left = distances.get('left')
                    distance_right = distances.get('right')

                # Format text for overlay
                text_front = f"Front: {distance_front if distance_front is not None else 'N/A'} cm"
                text_left = f"Left: {distance_left if distance_left is not None else 'N/A'} cm"
                text_right = f"Right: {distance_right if distance_right is not None else 'N/A'} cm"

                # Overlay text on the frame with adjusted positions
                cv2.putText(frame, text_front, (5, 15), font, font_scale, color, thickness, line_type)
                cv2.putText(frame, text_left, (5, 30), font, font_scale, color, thickness, line_type)
                cv2.putText(frame, text_right, (5, 45), font, font_scale, color, thickness, line_type)

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
        picam2.stop()
        logger.info("Camera stopped.")
