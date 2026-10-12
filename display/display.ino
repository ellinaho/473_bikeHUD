#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <SPI.h>


#define TFT_CS  10
#define TFT_RST 9
#define TFT_DC  8

Adafruit_ST7735 tft(TFT_CS, TFT_DC, TFT_RST);

// mirror helper function to undo effect from optics
void setMirrorX(bool mirror) {
  uint8_t madctl = ST77XX_MADCTL_MY | ST77XX_MADCTL_MV | ST7735_MADCTL_BGR;
  if (mirror) madctl |= ST77XX_MADCTL_MX;
  tft.sendCommand(ST77XX_MADCTL, &madctl, 1);
}

void setup() {
  tft.initR(INITR_MINI160x80_PLUGIN);  // for 0.96" 80x160 IPS
  tft.setRotation(1);                  // landscape, 160x80
  setMirrorX(true);                    // undo the HUD's left-right flip
  tft.fillScreen(ST77XX_WHITE);

  tft.setTextColor(ST77XX_BLACK);
  tft.setTextSize(2);
  tft.setCursor(40, 55);
  tft.print("SixLabs");

  tft.setTextSize(1);
  tft.setCursor(30, 0);
  tft.print("9:30 PM");

  tft.setTextSize(1);
  tft.setCursor(100, 0);
  tft.print("20 MPH");

  //tft.drawRect(0, 0, 160, 80, ST77XX_GREEN);
}

void loop() {}
