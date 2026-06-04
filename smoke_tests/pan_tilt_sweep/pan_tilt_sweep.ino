#include <Arduino.h>
#include <ESP32Servo.h>

static const int PAN_SERVO_PIN = 18;
static const int TILT_SERVO_PIN = 19;
static const int SERVO_MIN_US = 500;
static const int SERVO_MAX_US = 2500;
static const int PAN_MIN_DEG = 45;
static const int PAN_CENTER_DEG = 90;
static const int PAN_MAX_DEG = 135;
static const int TILT_MIN_DEG = 60;
static const int TILT_CENTER_DEG = 90;
static const int TILT_MAX_DEG = 120;

static Servo panServo;
static Servo tiltServo;

static void moveBoth(int panDeg, int tiltDeg, int holdMs) {
  panServo.write(panDeg);
  tiltServo.write(tiltDeg);
  Serial.print("pan ");
  Serial.print(panDeg);
  Serial.print(" tilt ");
  Serial.println(tiltDeg);
  delay(holdMs);
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println("Pan tilt sweep smoke test");
  Serial.println("Use external servo power and common ground.");

  panServo.setPeriodHertz(50);
  tiltServo.setPeriodHertz(50);
  panServo.attach(PAN_SERVO_PIN, SERVO_MIN_US, SERVO_MAX_US);
  tiltServo.attach(TILT_SERVO_PIN, SERVO_MIN_US, SERVO_MAX_US);
  moveBoth(PAN_CENTER_DEG, TILT_CENTER_DEG, 1500);
}

void loop() {
  moveBoth(PAN_MIN_DEG, TILT_CENTER_DEG, 900);
  moveBoth(PAN_CENTER_DEG, TILT_CENTER_DEG, 900);
  moveBoth(PAN_MAX_DEG, TILT_CENTER_DEG, 900);
  moveBoth(PAN_CENTER_DEG, TILT_MIN_DEG, 900);
  moveBoth(PAN_CENTER_DEG, TILT_CENTER_DEG, 900);
  moveBoth(PAN_CENTER_DEG, TILT_MAX_DEG, 900);
}
