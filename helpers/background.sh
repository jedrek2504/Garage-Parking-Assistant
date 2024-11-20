#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Define variables for filenames
TEMP_BG="background_frame_temp.jpg"
FINAL_BG="background_frame_flipped_swapped.jpg"

# Function to capture background image
capture_background() {
    echo "Capturing background image..."
    libcamera-still -o "$TEMP_BG" --width 640 --height 480
    echo "Background image captured as $TEMP_BG."
}

# Function to flip the image horizontally and vertically and swap R and B channels
flip_and_swap_channels() {
    echo "Flipping the image horizontally and vertically, and swapping Red and Blue channels..."
    ffmpeg -i "$TEMP_BG" -vf "hflip,vflip,colorchannelmixer=rr=0:rg=0:rb=1:gr=0:gg=1:gb=0:br=1:bg=0:bb=0" "$FINAL_BG" -y
    echo "Image flipped and color channels swapped. Saved as $FINAL_BG."
}

# Function to clean up temporary files
cleanup() {
    echo "Cleaning up temporary files..."
    rm -f "$TEMP_BG"
    echo "Temporary files removed."
}

# Main execution flow
main() {
    capture_background
    flip_and_swap_channels

    # Remove existing background_frame.jpg if it exists
    if [ -f "background_frame.jpg" ]; then
        echo "Removing existing background_frame.jpg..."
        rm -f background_frame.jpg
    fi

    mv "$FINAL_BG" "background_frame.jpg"
    echo "Background image saved as background_frame.jpg."

    cleanup
    echo "Background frame capture and processing completed successfully."
}

# Execute the main function
main
