# camera_stream.py

from flask import Flask, Response
from picamera2 import Picamera2
import cv2

def run_flask_app():
    app = Flask(__name__)

    # Initialize Picamera2 outside the generator function
    picam2 = Picamera2()
    video_config = picam2.create_video_configuration(
        main={"size": (320, 240)},
        controls={"FrameDurationLimits": (33333, 33333)}  # Set to ~30 FPS
    )
    picam2.configure(video_config)
    picam2.start()

    def gen_frames():
        try:
            while True:
                # Capture frame-by-frame
                frame = picam2.capture_array()

                # Optional: Remove color conversion if not needed
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                # Encode the frame in JPEG format with reduced quality
                ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                if not ret:
                    continue  # Skip the frame if encoding failed

                # Convert the frame to bytes and yield it
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        except GeneratorExit:
            # Handle generator exit when client disconnects
            pass
        except Exception as e:
            print(f"Exception in gen_frames: {e}")

    @app.route('/video_feed')
    def video_feed():
        # Return the response generated along with the specific media type (mime type)
        return Response(gen_frames(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')

    try:
        app.run(host='0.0.0.0', port=5000)
    except Exception as e:
        print(f"Exception in Flask app: {e}")
    finally:
        picam2.stop()
        print("Camera stopped.")
