#include <Arduino.h>
#include <WiFi.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>
#include "wifi_secrets.h"

static const int SERVER_PORT = 5006;
static const int PAN_SERVO_PIN = 18;
static const int TILT_SERVO_PIN = 19;
static const int LOCK_LED_PIN = 23;
static const int AUX_OUTPUT_PIN = 25;

static const int SERVO_MIN_US = 500;
static const int SERVO_MAX_US = 2500;
static const float PAN_MIN_DEG = 30.0f;
static const float PAN_CENTER_DEG = 90.0f;
static const float PAN_MAX_DEG = 150.0f;
static const float TILT_MIN_DEG = 45.0f;
static const float TILT_CENTER_DEG = 90.0f;
static const float TILT_MAX_DEG = 135.0f;
static const float MAX_SLEW_DEG_PER_SEC = 180.0f;
static const uint32_t HEARTBEAT_TIMEOUT_MS = 750;
static const uint32_t WIFI_CONNECT_TIMEOUT_MS = 30000;
static const size_t RX_BUFFER_SIZE = 384;

static WiFiServer server(SERVER_PORT);
static WiFiClient client;
static Servo panServo;
static Servo tiltServo;

static float currentPanDeg = PAN_CENTER_DEG;
static float currentTiltDeg = TILT_CENTER_DEG;
static float targetPanDeg = PAN_CENTER_DEG;
static float targetTiltDeg = TILT_CENTER_DEG;
static bool lockLedOn = false;
static bool auxOutputOn = false;
static uint32_t lastCommandMs = 0;
static uint32_t lastMotionMs = 0;
static char rxBuffer[RX_BUFFER_SIZE];
static size_t rxIndex = 0;

static float clampFloat(float value, float low, float high) {
  if (value < low) {
    return low;
  }
  if (value > high) {
    return high;
  }
  return value;
}

static float moveToward(float current, float target, float maxDelta) {
  const float delta = target - current;
  if (fabs(delta) <= maxDelta) {
    return target;
  }
  return current + (delta > 0.0f ? maxDelta : -maxDelta);
}

static void writeStatusOutputs() {
  digitalWrite(LOCK_LED_PIN, lockLedOn ? HIGH : LOW);
  digitalWrite(AUX_OUTPUT_PIN, auxOutputOn ? HIGH : LOW);
}

static void centerTargets() {
  targetPanDeg = PAN_CENTER_DEG;
  targetTiltDeg = TILT_CENTER_DEG;
  lockLedOn = false;
  auxOutputOn = false;
  writeStatusOutputs();
}

static void sendStatus(WiFiClient &out) {
  JsonDocument doc;
  doc["ok"] = true;
  doc["pan"] = currentPanDeg;
  doc["tilt"] = currentTiltDeg;
  doc["target_pan"] = targetPanDeg;
  doc["target_tilt"] = targetTiltDeg;
  doc["lock"] = lockLedOn;
  doc["aux"] = auxOutputOn;
  doc["uptime_ms"] = millis();
  serializeJson(doc, out);
  out.print('\n');
}

static void sendError(WiFiClient &out, const char *message) {
  JsonDocument doc;
  doc["ok"] = false;
  doc["error"] = message;
  serializeJson(doc, out);
  out.print('\n');
}

static void handleCommandLine(const char *line) {
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, line);
  if (err) {
    if (client && client.connected()) {
      sendError(client, "invalid json");
    }
    return;
  }

  const char *type = doc["type"] | "target";
  lastCommandMs = millis();

  if (strcmp(type, "heartbeat") == 0) {
    if (client && client.connected()) {
      sendStatus(client);
    }
    return;
  }

  if (strcmp(type, "center") == 0) {
    centerTargets();
    if (client && client.connected()) {
      sendStatus(client);
    }
    return;
  }

  if (strcmp(type, "target") != 0) {
    if (client && client.connected()) {
      sendError(client, "unknown command");
    }
    return;
  }

  if (doc["pan"].is<float>()) {
    targetPanDeg = clampFloat(doc["pan"].as<float>(), PAN_MIN_DEG, PAN_MAX_DEG);
  }
  if (doc["tilt"].is<float>()) {
    targetTiltDeg = clampFloat(doc["tilt"].as<float>(), TILT_MIN_DEG, TILT_MAX_DEG);
  }
  if (doc["lock"].is<bool>()) {
    lockLedOn = doc["lock"].as<bool>();
  }
  if (doc["aux"].is<bool>()) {
    auxOutputOn = doc["aux"].as<bool>();
  }

  writeStatusOutputs();
  if (client && client.connected()) {
    sendStatus(client);
  }
}

static bool connectWifi() {
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
}

static void updateServos() {
  const uint32_t nowMs = millis();
  const float dtSec = max(0.001f, static_cast<float>(nowMs - lastMotionMs) / 1000.0f);
  lastMotionMs = nowMs;

  const float maxDelta = MAX_SLEW_DEG_PER_SEC * dtSec;
  currentPanDeg = moveToward(currentPanDeg, targetPanDeg, maxDelta);
  currentTiltDeg = moveToward(currentTiltDeg, targetTiltDeg, maxDelta);

  panServo.write(static_cast<int>(roundf(currentPanDeg)));
  tiltServo.write(static_cast<int>(roundf(currentTiltDeg)));
}

static void checkHeartbeat() {
  if (lastCommandMs == 0) {
    return;
  }

  if (millis() - lastCommandMs <= HEARTBEAT_TIMEOUT_MS) {
    return;
  }

  lockLedOn = false;
  auxOutputOn = false;
  writeStatusOutputs();
}

static void readClientLines() {
  while (client && client.connected() && client.available()) {
    const char value = static_cast<char>(client.read());
    if (value == '\r') {
      continue;
    }
    if (value == '\n') {
      rxBuffer[rxIndex] = '\0';
      if (rxIndex > 0) {
        handleCommandLine(rxBuffer);
      }
      rxIndex = 0;
      continue;
    }
    if (rxIndex < RX_BUFFER_SIZE - 1) {
      rxBuffer[rxIndex++] = value;
    } else {
      rxIndex = 0;
      sendError(client, "line too long");
    }
  }
}

static void acceptClient() {
  if (client && client.connected()) {
    return;
  }

  if (client) {
    client.stop();
  }

  WiFiClient nextClient = server.available();
  if (!nextClient) {
    return;
  }

  client = nextClient;
  client.setNoDelay(true);
  rxIndex = 0;
  lastCommandMs = millis();
  Serial.print("client connected: ");
  Serial.println(client.remoteIP());
  sendStatus(client);
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println("ESP32 pan tilt tracker controller");

  pinMode(LOCK_LED_PIN, OUTPUT);
  pinMode(AUX_OUTPUT_PIN, OUTPUT);
  writeStatusOutputs();

  panServo.setPeriodHertz(50);
  tiltServo.setPeriodHertz(50);
  panServo.attach(PAN_SERVO_PIN, SERVO_MIN_US, SERVO_MAX_US);
  tiltServo.attach(TILT_SERVO_PIN, SERVO_MIN_US, SERVO_MAX_US);
  panServo.write(static_cast<int>(PAN_CENTER_DEG));
  tiltServo.write(static_cast<int>(TILT_CENTER_DEG));
  lastMotionMs = millis();

  if (!connectWifi()) {
    Serial.println("wifi setup stopped");
    return;
  }

  server.begin();
  server.setNoDelay(true);
  Serial.printf("command server ready: %s:%d\n", WiFi.localIP().toString().c_str(), SERVER_PORT);
}

void loop() {
  acceptClient();
  readClientLines();
  checkHeartbeat();
  updateServos();
  delay(10);
}
