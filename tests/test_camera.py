from flask import Flask, Response
import cv2
from picamera2 import Picamera2

app = Flask(__name__)

# Initialize camera using Picamera2
picam2 = Picamera2()
video_config = picam2.create_video_configuration(main={"size": (640, 480)}, controls={"FrameRate": 15})
picam2.configure(video_config)
picam2.start()

def generate_frames():
    while True:
        try:
            # Capture frame from the camera
            frame = picam2.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            # Flip the frame upside down
            frame = cv2.flip(frame, 0)

            # Encode frame to JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()

            # Yield frame in byte format
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        except Exception as e:
            print(f"Error: {e}")
            break

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        picam2.stop()
