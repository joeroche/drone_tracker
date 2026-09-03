#include <Arduino.h>
#include <ESP32Servo.h>
#include <WiFi.h>

static const char *WIFI_SSID = "DroneTracker";
static const char *WIFI_PASSWORD = "dronetrack";
static const uint16_t TCP_PORT = 5006;
static const int PAN_SERVO_PIN = 18;
static const int TILT_SERVO_PIN = 19;
static const int SERVO_MIN_US = 500;
static const int SERVO_MAX_US = 2500;
static const uint32_t COMMAND_TIMEOUT_MS = 750;

static WiFiServer server(TCP_PORT);
static WiFiClient client;
static Servo panServo;
static Servo tiltServo;
static uint8_t commandState = 0;
static uint8_t pendingPan = 90;
static uint32_t lastCommandMs = 0;

static void centerServos() {
  panServo.write(90);
  tiltServo.write(90);
}

static void consumeCommands(WiFiClient &input) {
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
        lastCommandMs = millis();
        commandState = 0;
        break;
    }
  }
}

void setup() {
  Serial.begin(115200);
  panServo.setPeriodHertz(50);
  tiltServo.setPeriodHertz(50);
  panServo.attach(PAN_SERVO_PIN, SERVO_MIN_US, SERVO_MAX_US);
  tiltServo.attach(TILT_SERVO_PIN, SERVO_MIN_US, SERVO_MAX_US);
  centerServos();

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.config(
    IPAddress(192, 168, 4, 2),
    IPAddress(192, 168, 4, 1),
    IPAddress(255, 255, 255, 0)
  );
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
  }
  server.begin();
  server.setNoDelay(true);
  Serial.printf("tracker controller listening at %s:%u\n", WiFi.localIP().toString().c_str(), TCP_PORT);
}

void loop() {
  if (!client || !client.connected()) {
    if (client) {
      client.stop();
    }
    client = server.available();
    commandState = 0;
  }
  if (client && client.connected()) {
    consumeCommands(client);
  }
  if (lastCommandMs != 0 && millis() - lastCommandMs > COMMAND_TIMEOUT_MS) {
    centerServos();
    lastCommandMs = 0;
  }
  delay(1);
}
