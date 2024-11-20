#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Capture a temporary background image
echo "Capturing background image..."
libcamera-still -o background_frame_temp.jpg --width 640 --height 480

# Remove existing background_frame.jpg if it exists
if [ -f "background_frame.jpg" ]; then
    echo "Removing existing background_frame.jpg..."
    rm -f background_frame.jpg
fi

# Flip the image using ffmpeg
echo "Flipping the image..."
ffmpeg -i background_frame_temp.jpg -vf "hflip,vflip" background_frame.jpg -y

# Remove the temporary image
echo "Cleaning up temporary files..."
rm -f background_frame_temp.jpg

echo "Background image saved as background_frame.jpg."
