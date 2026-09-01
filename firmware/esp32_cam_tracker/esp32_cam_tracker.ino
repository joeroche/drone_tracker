#include <Arduino.h>
#include <ESP32Servo.h>
#include <WiFi.h>
#include "esp_camera.h"
#include "camera_pins.h"

static const char *AP_SSID = "DroneTracker";
static const char *AP_PASSWORD = "dronetrack";
static const uint8_t AP_CHANNEL = 6;
static const uint16_t TCP_PORT = 5005;
static const uint8_t TARGET_FPS = 10;

static const int PAN_SERVO_PIN = 14;
static const int TILT_SERVO_PIN = 15;
static const int SERVO_MIN_US = 500;
static const int SERVO_MAX_US = 2500;

static WiFiServer server(TCP_PORT);
static WiFiClient client;
static Servo panServo;
static Servo tiltServo;
static uint32_t lastFrameMs = 0;
static uint8_t commandState = 0;
static uint8_t pendingPan = 90;

static bool writeAll(WiFiClient &out, const uint8_t *data, size_t length) {
  size_t sent = 0;
  while (sent < length && out.connected()) {
    const size_t count = out.write(data + sent, length - sent);
    if (count == 0) {
      delay(1);
      continue;
    }
    sent += count;
  }
  return sent == length;
}

static bool sendFrame(WiFiClient &out) {
  camera_fb_t *frame = esp_camera_fb_get();
  if (frame == nullptr) {
    Serial.println("camera capture failed");
    return false;
  }
  const uint32_t size = static_cast<uint32_t>(frame->len);
  const uint8_t header[6] = {
    0xFF,
    0xAA,
    static_cast<uint8_t>(size & 0xFF),
    static_cast<uint8_t>((size >> 8) & 0xFF),
    static_cast<uint8_t>((size >> 16) & 0xFF),
    static_cast<uint8_t>((size >> 24) & 0xFF),
  };
  const bool ok = writeAll(out, header, sizeof(header))
    && writeAll(out, frame->buf, frame->len);
  esp_camera_fb_return(frame);
  return ok;
}

static void consumeServoCommands(WiFiClient &input) {
  while (input.available()) {
    const uint8_t value = static_cast<uint8_t>(input.read());
    switch (commandState) {
      case 0:
        commandState = value == 0xBB ? 1 : 0;
        break;
      case 1:
        commandState = value == 0xCC ? 2 : (value == 0xBB ? 1 : 0);
        break;
      case 2:
        pendingPan = value;
        commandState = 3;
        break;
      case 3:
        panServo.write(constrain(static_cast<int>(pendingPan), 0, 180));
        tiltServo.write(constrain(static_cast<int>(value), 0, 180));
        commandState = 0;
        break;
    }
  }
}

static bool initializeCamera() {
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_QVGA;
  config.jpeg_quality = 12;
  config.fb_location = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
  config.fb_count = psramFound() ? 2 : 1;
  config.grab_mode = psramFound() ? CAMERA_GRAB_LATEST : CAMERA_GRAB_WHEN_EMPTY;
  return esp_camera_init(&config) == ESP_OK;
}

void setup() {
  Serial.begin(115200);
  delay(200);
  if (!initializeCamera()) {
    Serial.println("camera initialization failed");
    return;
  }

  panServo.setPeriodHertz(50);
  tiltServo.setPeriodHertz(50);
  panServo.attach(PAN_SERVO_PIN, SERVO_MIN_US, SERVO_MAX_US);
  tiltServo.attach(TILT_SERVO_PIN, SERVO_MIN_US, SERVO_MAX_US);
  panServo.write(90);
  tiltServo.write(90);

  WiFi.mode(WIFI_AP);
  WiFi.setSleep(false);
  if (!WiFi.softAP(AP_SSID, AP_PASSWORD, AP_CHANNEL, false, 1)) {
    Serial.println("access point startup failed");
    return;
  }
  server.begin();
  server.setNoDelay(true);
  Serial.printf("join %s and connect to %s:%u\n", AP_SSID, WiFi.softAPIP().toString().c_str(), TCP_PORT);
}

void loop() {
  if (!client || !client.connected()) {
    if (client) {
      client.stop();
    }
    client = server.available();
    if (!client) {
      delay(2);
      return;
    }
    client.setNoDelay(true);
    commandState = 0;
    Serial.println("Mac connected");
  }

  consumeServoCommands(client);
  const uint32_t nowMs = millis();
  if (nowMs - lastFrameMs >= 1000U / TARGET_FPS) {
    lastFrameMs = nowMs;
    if (!sendFrame(client)) {
      client.stop();
    }
  }
  consumeServoCommands(client);
}
