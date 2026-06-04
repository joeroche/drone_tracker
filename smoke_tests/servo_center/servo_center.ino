#include <ESP32Servo.h>

const int SERVO_PIN = 19;
const int CENTER_DEG = 90;
const int MIN_DEG = 0;
const int MAX_DEG = 180;

Servo servo;

void setup() {
    Serial.begin(115200);

    servo.setPeriodHertz(50);
    servo.attach(SERVO_PIN, 500, 2500);
    servo.write(CENTER_DEG);

    Serial.println("MG996R angle tester on GPIO 19.");
    Serial.println("Centered at 90 degrees.");
    Serial.println("Type an angle from 0 to 180 and press Enter.");
}

void loop() {
    if (!Serial.available()) {
        return;
    }

    int angle = Serial.parseInt();

    while (Serial.available()) {
        Serial.read();
    }

    if (angle < MIN_DEG || angle > MAX_DEG) {
        Serial.println("Invalid angle. Use 0 to 180.");
        return;
    }

    servo.write(angle);
    Serial.print("Servo moved to ");
    Serial.print(angle);
    Serial.println(" degrees.");
}
