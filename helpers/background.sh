#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Define paths and filenames
HELPER_SCRIPT="./helpers/capture_background_helper.py"
TEMP_BG="background_frame_temp.jpg"
FINAL_BG="background_frame_flipped_swapped.jpg"
OUTPUT_BG="./background_frame.jpg"

# Function to run the helper script and capture the background
run_helper_and_capture() {
    echo "Running helper script: $HELPER_SCRIPT"
    sudo .venv/bin/python3 "$HELPER_SCRIPT" &  # Run the helper script in the background
    sleep 2  # Wait for 2 seconds before capturing the image
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

# Function to move the final image to the main folder
save_final_image() {
    # Remove existing background_frame.jpg if it exists
    if [ -f "$OUTPUT_BG" ]; then
        echo "Removing existing background_frame.jpg..."
        rm -f "$OUTPUT_BG"
    fi

    mv "$FINAL_BG" "$OUTPUT_BG"
    echo "Background image saved as $OUTPUT_BG."
}

# Function to clean up temporary files
cleanup() {
    echo "Cleaning up temporary files..."
    rm -f "$TEMP_BG"
    echo "Temporary files removed."
}

# Main execution flow
main() {
    run_helper_and_capture
    flip_and_swap_channels
    save_final_image
    cleanup
    echo "Background frame capture and processing completed successfully."
}

# Execute the main function
main
