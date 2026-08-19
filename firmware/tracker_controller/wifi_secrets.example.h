#pragma once

const char *WIFI_SSID = "your_wifi_name";
const char *WIFI_PASSWORD = "your_wifi_password";

// Set to 1 when connecting to the ESP32-CAM access point.
#define WIFI_USE_STATIC_IP 0
#define WIFI_LOCAL_IP IPAddress(192, 168, 4, 20)
#define WIFI_GATEWAY IPAddress(192, 168, 4, 1)
#define WIFI_SUBNET IPAddress(255, 255, 255, 0)
