import os
import cv2
import numpy as np

# Directories
TEST_FRAMES_DIR = "test_frames"
OUTPUT_FRAMES_DIR = "output_frames"

# Constants
ROI_TOP_LEFT = (110, 60)
ROI_BOTTOM_RIGHT = (550, 470)

# Load background frame for analysis
BACKGROUND_FRAME_PATH = "background_frame.jpg"
background_frame = cv2.imread(BACKGROUND_FRAME_PATH)
if background_frame is None:
    raise FileNotFoundError(f"Background frame not found at {BACKGROUND_FRAME_PATH}")

# Extract background ROI
background_roi = background_frame[
    ROI_TOP_LEFT[1]:ROI_BOTTOM_RIGHT[1], ROI_TOP_LEFT[0]:ROI_BOTTOM_RIGHT[0]
]

def process_frame(frame, background_roi, roi_top_left, roi_bottom_right):
    """
    Perform AI analysis to detect objects by comparing the current frame's ROI
    with the background ROI.
    """
    # Extract ROI from the frame
    roi = frame[roi_top_left[1]:roi_bottom_right[1], roi_top_left[0]:roi_bottom_right[0]]

    # Calculate absolute difference with the background
    diff = cv2.absdiff(roi, background_roi)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

    # Threshold to create a binary foreground mask
    _, fg_mask = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)

    # Morphological operations to clean up the mask
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=2)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_DILATE, kernel, iterations=1)

    # Find contours to detect objects
    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    detections = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 500:  # Threshold for valid obstacles
            x, y, w, h = cv2.boundingRect(cnt)
            detections.append((x + roi_top_left[0], y + roi_top_left[1],
                               x + roi_top_left[0] + w, y + roi_top_left[1] + h))

    return detections

def process_test_frames():
    """
    Process all frames in the test_frames directory and save processed frames
    with detected obstacles to the output_frames directory.
    """
    for frame_name in os.listdir(TEST_FRAMES_DIR):
        frame_path = os.path.join(TEST_FRAMES_DIR, frame_name)

        if not frame_name.lower().endswith(('.png', '.jpg', '.jpeg')):
            continue  # Skip non-image files

        # Read the frame
        frame = cv2.imread(frame_path)
        if frame is None:
            print(f"Failed to load frame: {frame_path}")
            continue

        # Perform AI analysis
        detections = process_frame(frame, background_roi, ROI_TOP_LEFT, ROI_BOTTOM_RIGHT)

        # Draw the ROI and obstacles
        cv2.rectangle(frame, ROI_TOP_LEFT, ROI_BOTTOM_RIGHT, (0, 255, 0), 2)  # ROI in green
        for x1, y1, x2, y2 in detections:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)  # Obstacles in red
            cv2.putText(frame, "Obstacle", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        # Save the processed frame
        output_path = os.path.join(OUTPUT_FRAMES_DIR, frame_name)
        cv2.imwrite(output_path, frame)
        print(f"Processed and saved: {output_path}")

if __name__ == "__main__":
    # Ensure output directory exists
    os.makedirs(OUTPUT_FRAMES_DIR, exist_ok=True)

    # Process test frames
    process_test_frames()
