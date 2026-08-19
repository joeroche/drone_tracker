#include <Arduino.h>
#include <WiFi.h>
#include "esp_camera.h"
#include "esp_http_server.h"
#include "esp_timer.h"
#include "wifi_secrets.h"

#define CAMERA_MODEL_AI_THINKER

#define PWDN_GPIO_NUM 32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 0
#define SIOD_GPIO_NUM 26
#define SIOC_GPIO_NUM 27
#define Y9_GPIO_NUM 35
#define Y8_GPIO_NUM 34
#define Y7_GPIO_NUM 39
#define Y6_GPIO_NUM 36
#define Y5_GPIO_NUM 21
#define Y4_GPIO_NUM 19
#define Y3_GPIO_NUM 18
#define Y2_GPIO_NUM 5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM 23
#define PCLK_GPIO_NUM 22

static const int MJPEG_PORT = 81;
static const int TCP_JPEG_PORT = 5005;
static const bool ENABLE_TCP_JPEG_STREAM = true;
static const uint32_t TCP_MAGIC = 0x44534A50UL;
static const uint8_t TCP_VERSION = 1;
static const uint32_t WIFI_CONNECT_TIMEOUT_MS = 30000;

#ifndef WIFI_AP_MODE
#define WIFI_AP_MODE 0
#endif

#ifndef WIFI_AP_CHANNEL
#define WIFI_AP_CHANNEL 6
#endif

#ifndef WIFI_AP_MAX_CONNECTIONS
#define WIFI_AP_MAX_CONNECTIONS 4
#endif

#ifndef WIFI_AP_IP
#define WIFI_AP_IP IPAddress(192, 168, 4, 1)
#endif

#ifndef WIFI_AP_GATEWAY
#define WIFI_AP_GATEWAY IPAddress(192, 168, 4, 1)
#endif

#ifndef WIFI_AP_SUBNET
#define WIFI_AP_SUBNET IPAddress(255, 255, 255, 0)
#endif

static WiFiServer tcpServer(TCP_JPEG_PORT);
static httpd_handle_t streamServer = nullptr;
static uint32_t frameSequence = 0;

static const char *STREAM_BOUNDARY = "123456789000000000000987654321";
static const char *STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=123456789000000000000987654321";
static const char *STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\nX-Sequence: %u\r\nX-Timestamp-Us: %llu\r\n\r\n";

static IPAddress localNetworkIp() {
#if WIFI_AP_MODE
  return WiFi.softAPIP();
#else
  return WiFi.localIP();
#endif
}

static void writeUint32(WiFiClient &client, uint32_t value) {
  uint8_t bytes[4] = {
    static_cast<uint8_t>((value >> 24) & 0xFF),
    static_cast<uint8_t>((value >> 16) & 0xFF),
    static_cast<uint8_t>((value >> 8) & 0xFF),
    static_cast<uint8_t>(value & 0xFF)
  };
  client.write(bytes, sizeof(bytes));
}

static void writeUint64(WiFiClient &client, uint64_t value) {
  uint8_t bytes[8];
  for (int i = 7; i >= 0; i -= 1) {
    bytes[7 - i] = static_cast<uint8_t>((value >> (i * 8)) & 0xFF);
  }
  client.write(bytes, sizeof(bytes));
}

static bool initCamera() {
  camera_config_t config;
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
  config.frame_size = FRAMESIZE_VGA;
  config.jpeg_quality = 12;
  config.fb_count = 1;
  config.fb_location = CAMERA_FB_IN_DRAM;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;

  if (psramFound()) {
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.fb_count = 2;
    config.grab_mode = CAMERA_GRAB_LATEST;
    config.jpeg_quality = 10;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("camera init failed: 0x%x\n", err);
    return false;
  }

  sensor_t *sensor = esp_camera_sensor_get();
  if (sensor != nullptr) {
    sensor->set_framesize(sensor, FRAMESIZE_VGA);
    sensor->set_brightness(sensor, 0);
    sensor->set_saturation(sensor, -1);
  }

  return true;
}

static esp_err_t streamHandler(httpd_req_t *req) {
  esp_err_t res = httpd_resp_set_type(req, STREAM_CONTENT_TYPE);
  if (res != ESP_OK) {
    return res;
  }

  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

  while (true) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (fb == nullptr) {
      Serial.println("camera capture failed");
      return ESP_FAIL;
    }

    const uint32_t seq = ++frameSequence;
    const uint64_t timestampUs = static_cast<uint64_t>(esp_timer_get_time());
    char partHeader[128];
    const int headerLen = snprintf(
      partHeader,
      sizeof(partHeader),
      STREAM_PART,
      static_cast<unsigned int>(fb->len),
      static_cast<unsigned int>(seq),
      static_cast<unsigned long long>(timestampUs)
    );

    res = httpd_resp_send_chunk(req, "\r\n-" "-", 4);
    if (res == ESP_OK) {
      res = httpd_resp_send_chunk(req, STREAM_BOUNDARY, strlen(STREAM_BOUNDARY));
    }
    if (res == ESP_OK) {
      res = httpd_resp_send_chunk(req, "\r\n", 2);
    }
    if (res == ESP_OK) {
      res = httpd_resp_send_chunk(req, partHeader, headerLen);
    }
    if (res == ESP_OK) {
      res = httpd_resp_send_chunk(req, reinterpret_cast<const char *>(fb->buf), fb->len);
    }

    esp_camera_fb_return(fb);

    if (res != ESP_OK) {
      return res;
    }

    delay(1);
  }
}

static void startMjpegServer() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = MJPEG_PORT;
  config.ctrl_port = MJPEG_PORT + 1;

  httpd_uri_t streamUri = {};
  streamUri.uri = "/stream";
  streamUri.method = HTTP_GET;
  streamUri.handler = streamHandler;
  streamUri.user_ctx = nullptr;

  if (httpd_start(&streamServer, &config) == ESP_OK) {
    httpd_register_uri_handler(streamServer, &streamUri);
    Serial.printf("mjpeg stream ready: http://%s:%d/stream\n", localNetworkIp().toString().c_str(), MJPEG_PORT);
  } else {
    Serial.println("mjpeg server failed");
  }
}

static bool connectWifi() {
#if WIFI_AP_MODE
  WiFi.mode(WIFI_AP);
  WiFi.setSleep(false);
  WiFi.softAPConfig(WIFI_AP_IP, WIFI_AP_GATEWAY, WIFI_AP_SUBNET);
  if (!WiFi.softAP(WIFI_SSID, WIFI_PASSWORD, WIFI_AP_CHANNEL, 0, WIFI_AP_MAX_CONNECTIONS)) {
    Serial.println("wifi ap start failed");
    return false;
  }

  Serial.print("wifi ap ready: ");
  Serial.println(WiFi.softAPIP());
  return true;
#else
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print("wifi connecting");
  const uint32_t startMs = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startMs < WIFI_CONNECT_TIMEOUT_MS) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("wifi connect timeout");
    return false;
  }

  Serial.print("wifi connected: ");
  Serial.println(WiFi.localIP());
  return true;
#endif
}

static void serveTcpJpegClient(WiFiClient &client) {
  Serial.print("tcp jpeg client: ");
  Serial.println(client.remoteIP());
  client.setNoDelay(true);

  while (client.connected()) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (fb == nullptr) {
      Serial.println("camera capture failed");
      delay(25);
      continue;
    }

    const uint32_t seq = ++frameSequence;
    const uint64_t timestampUs = static_cast<uint64_t>(esp_timer_get_time());
    writeUint32(client, TCP_MAGIC);
    client.write(TCP_VERSION);
    client.write(static_cast<uint8_t>(0));
    client.write(static_cast<uint8_t>(0));
    client.write(static_cast<uint8_t>(0));
    writeUint32(client, seq);
    writeUint64(client, timestampUs);
    writeUint32(client, static_cast<uint32_t>(fb->len));
    client.write(fb->buf, fb->len);
    esp_camera_fb_return(fb);

    if (!client.connected()) {
      break;
    }
    delay(1);
  }

  client.stop();
  Serial.println("tcp jpeg client disconnected");
}

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(false);
  delay(200);
  Serial.println();
  Serial.println("AI Thinker ESP32-CAM tracker stream");

  if (!initCamera()) {
    Serial.println("camera setup stopped");
    return;
  }

  if (!connectWifi()) {
    Serial.println("wifi setup stopped");
    return;
  }

  startMjpegServer();
  if (ENABLE_TCP_JPEG_STREAM) {
    tcpServer.begin();
    tcpServer.setNoDelay(true);
    Serial.printf("tcp jpeg stream ready: %s:%d\n", localNetworkIp().toString().c_str(), TCP_JPEG_PORT);
  }
}

void loop() {
  if (!ENABLE_TCP_JPEG_STREAM) {
    delay(1000);
    return;
  }

  WiFiClient client = tcpServer.available();
  if (client) {
    serveTcpJpegClient(client);
  }

  delay(5);
}
