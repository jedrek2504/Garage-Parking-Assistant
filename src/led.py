# import board
# import neopixel
# import logging

# # Konfiguracja paska LED
# LED_COUNT = 60  # Ilość diod na pasku
# LED_PIN = board.D18  # Pin danych dla WS2812B (GPIO 18)
# ORDER = neopixel.GRB  # Kolejność kolorów

# pixels = neopixel.NeoPixel(LED_PIN, LED_COUNT, brightness=0.5, auto_write=False, pixel_order=ORDER)

# def ustaw_led_kolor(odleglosc):
#     if odleglosc < 10:
#         logging.info("Odległość < 10 cm: LED na czerwono")
#         pixels.fill((255, 0, 0))  # Czerwony
#     elif 10 <= odleglosc < 30:
#         logging.info("Odległość między 10 cm a 30 cm: LED na żółto")
#         pixels.fill((255, 255, 0))  # Żółty
#     else:
#         logging.info("Odległość >= 30 cm: LED na zielono")
#         pixels.fill((0, 255, 0))  # Zielony
#     pixels.show()
