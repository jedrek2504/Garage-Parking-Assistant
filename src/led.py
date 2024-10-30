import board
import neopixel

# LED strip configuration
LED_PIN = board.D18
NUM_LEDS = 60
CONTROL_LEDS = 15
BRIGHTNESS = 0.2
ORDER = neopixel.GRB

pixels = neopixel.NeoPixel(LED_PIN, NUM_LEDS, brightness=BRIGHTNESS, auto_write=False, pixel_order=ORDER)

def clear_leds():
    """Turns off all the LEDs."""
    for i in range(CONTROL_LEDS):
        pixels[i] = (0, 0, 0)
    pixels.show()

def set_led_color(r, g, b, brightness=255):
    """Set color and brightness for the provided number of LEDs."""
    adjusted_brightness = brightness / 255  # Normalize brightness to 0.0 - 1.0
    for i in range(CONTROL_LEDS):
        pixels[i] = (
            int(r * adjusted_brightness),
            int(g * adjusted_brightness),
            int(b * adjusted_brightness),
        )
    pixels.show()
