"""
AgriScan 360 - SSD1306 OLED Display Module
Renders classification results, confidence %, and gas levels on a 0.96" I2C OLED.
"""

try:
    from PIL import Image, ImageDraw, ImageFont
    import adafruit_ssd1306
    import board
    import busio
    OLED_AVAILABLE = True
except ImportError:
    OLED_AVAILABLE = False


class DisplayController:
    def __init__(self):
        self.oled = None
        self.is_connected = False

        if OLED_AVAILABLE:
            try:
                i2c = busio.I2C(board.SCL, board.SDA)
                self.oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)
                self.oled.fill(0)
                self.oled.show()
                self.is_connected = True
                print("[Display] SSD1306 OLED connected at 0x3C.")
            except Exception as e:
                print(f"[Display] OLED connection warning: {e}. Running in console mode.")
                self.is_connected = False
        else:
            print("[Display] Adafruit SSD1306 / Pillow not installed. Running in console mode.")

    def show_message(self, line1, line2="", line3=""):
        """Prints message to OLED (and mirrors to console)."""
        print(f"[OLED SCREEN] >> {line1} | {line2} | {line3}")

        if not self.is_connected:
            return

        try:
            image = Image.new("1", (128, 64))
            draw = ImageDraw.Draw(image)
            font = ImageFont.load_default()

            draw.text((0, 4),  str(line1), font=font, fill=255)
            draw.text((0, 22), str(line2), font=font, fill=255)
            draw.text((0, 42), str(line3), font=font, fill=255)

            self.oled.image(image)
            self.oled.show()
        except Exception as e:
            print(f"[Display] Draw error: {e}")

    def show_result(self, produce_name, classification, confidence, gas_delta):
        """Standardized scan result template."""
        line1 = f"{produce_name.upper()}"
        line2 = f"STATUS: {classification}"
        line3 = f"Conf: {confidence}% | dG:{gas_delta}k"
        self.show_message(line1, line2, line3)
