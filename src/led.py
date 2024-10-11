import board
import neopixel

# LED strip configuration
LED_PIN = board.D18  # GPIO pin connected to the DIN of the LED strip
NUM_LEDS = 60        # Total number of LEDs in the strip
CONTROL_LEDS = 15    # Number of LEDs to control
BRIGHTNESS = 0.2     # Set brightness level (0.0 to 1.0) for low power usage
ORDER = neopixel.GRB  # Order of colors (Green, Red, Blue for WS2812B)

# Create a NeoPixel object
pixels = neopixel.NeoPixel(LED_PIN, NUM_LEDS, brightness=BRIGHTNESS, auto_write=False, pixel_order=ORDER)

def set_led_color(r, g, b):
    """Sets the color of the first 15 LEDs."""
    for i in range(CONTROL_LEDS):
        pixels[i] = (r, g, b)
    pixels.show()

def set_led_based_on_distance(distance):
    """Sets LED colors based on the measured distance."""
    if distance < 10:
        set_led_color(255, 0, 0)  # Red for very close (danger)
    elif 10 <= distance < 20:
        set_led_color(255, 165, 0)  # Orange for medium distance (caution)
    else:
        set_led_color(0, 255, 0)  # Green for safe distance

def clear_leds():
    """Turns off all the LEDs."""
    set_led_color(0, 0, 0)
