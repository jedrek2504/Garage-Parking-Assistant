# src/garage_parking_assistant/camera_stream.py

from flask import Flask, Response
from shared_camera import SharedCamera
import cv2
import logging
import time
from exceptions import CameraError

def run_flask_app():
    """
    Run Flask app to stream camera feed.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] [Flask] %(message)s',
        handlers=[logging.StreamHandler()]
    )
    logger = logging.getLogger('FlaskApp')

    app = Flask(__name__)

    try:
        camera = SharedCamera.get_instance()
        logger.info("Camera accessed by Flask app.")
    except CameraError as e:
        logger.critical(f"Camera access failed: {e}")
        return  # Exit if camera fails

    def gen_frames():
        """
        Generator to yield camera frames.
        """
        try:
            while True:
                frame = camera.capture_array()
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                frame = cv2.flip(frame, -1)
                ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                if not ret:
                    logger.warning("Failed to encode frame.")
                    continue
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                time.sleep(0.066)  # ~15 FPS
        except GeneratorExit:
            logger.info("Client disconnected from video feed.")
        except CameraError as e:
            logger.critical(f"Camera error during frame generation: {e}")
        except Exception as e:
            logger.exception("Exception in frame generator.")
        finally:
            logger.info("Frame generation terminated.")

    @app.route('/video_feed')
    def video_feed():
        """
        Video feed route.
        """
        logger.info("Client connected to /video_feed.")
        return Response(gen_frames(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')

    try:
        app.run(host='0.0.0.0', port=5000)
    except Exception as e:
        logger.exception("Exception in Flask app.")
    finally:
        logger.info("Flask app terminated.")
