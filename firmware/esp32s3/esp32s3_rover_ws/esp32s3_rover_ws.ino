#include <Adafruit_MPU6050.h>
#include <Adafruit_HMC5883_U.h>
#include <Adafruit_Sensor.h>
#include <ArduinoJson.h>
#include <DNSServer.h>
#include <ESP32Servo.h>
#include <Preferences.h>
#include <WebServer.h>
#include <WebSocketsClient.h>
#include <WiFi.h>
#include <Wire.h>
#include <esp_system.h>
#include <math.h>
#include <string.h>

const char *SETUP_AP_SSID = "STASIS-ROVER-SETUP";
const char *SETUP_AP_PASSWORD = "stasis1234";
const char *FIRMWARE_BUILD_ID = __DATE__ " " __TIME__;

const uint16_t SERVER_PORT = 5000;
const char *WEBSOCKET_PATH = "/ws/rover";

const int A_IA = 26;
const int A_IB = 27;
const int B_IA = 14;
const int B_IB = 12;
const int SDA_PIN = 21;
const int SCL_PIN = 22;
const int ULTRASONIC_TRIG_PIN = 33;
const int ULTRASONIC_ECHO_PIN = 32;
const int SCANNER_SERVO_PIN = 13;

const float TURN_KP = 5.0;
const float TURN_TOLERANCE_DEG = 5.0;
const int TURN_MIN_PWM = 75;
const int TURN_MAX_PWM = 200;
const int DRIVE_PWM = 180;
const float DRIVE_MS_PER_CM = 50.0;  // Tune this on the real floor.
const unsigned long TELEMETRY_INTERVAL_MS = 500;
const int SCAN_STEP_DEG = 30;
const int SCAN_SETTLE_MS = 250;

const byte DNS_PORT = 53;

Adafruit_MPU6050 mpu;
Adafruit_HMC5883_Unified compass = Adafruit_HMC5883_Unified(12345);
DNSServer dnsServer;
Preferences prefs;
Servo scannerServo;
WebServer setupServer(80);
WebSocketsClient webSocket;

String serverIp = "";
String portalReason = "";
float yawDeg = 0.0;
float gyroZBias = 0.0;
unsigned long lastImuMs = 0;
unsigned long lastHeartbeatMs = 0;
unsigned long lastTelemetryMs = 0;
float distanceTraveledCm = 0.0;
bool imuReady = false;
bool compassReady = false;

void stopMotors();

String htmlEscape(const String &value) {
  String escaped = value;
  escaped.replace("&", "&amp;");
  escaped.replace("<", "&lt;");
  escaped.replace(">", "&gt;");
  escaped.replace("\"", "&quot;");
  return escaped;
}

String setupPage(const String &message = "") {
  String page = "<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>";
  page += "<title>STASIS Rover Setup</title><style>";
  page += "body{font-family:Arial,sans-serif;background:#111827;color:#f9fafb;margin:0;padding:24px}";
  page += "main{max-width:420px;margin:0 auto;background:#1f2937;border:1px solid #374151;border-radius:8px;padding:18px}";
  page += "label{display:block;margin:14px 0 6px}input{width:100%;padding:10px;border-radius:6px;border:1px solid #4b5563;background:#111827;color:#fff}";
  page += "button{margin-top:18px;width:100%;padding:12px;border:0;border-radius:6px;background:#2563eb;color:#fff;font-weight:bold}";
  page += ".msg{color:#fbbf24}</style></head><body><main><h2>STASIS Rover Setup</h2>";
  if (message.length()) page += "<p class='msg'>" + htmlEscape(message) + "</p>";
  page += "<form method='POST' action='/save'>";
  page += "<label>Wi-Fi SSID</label><input name='ssid' required autocomplete='off'>";
  page += "<label>Wi-Fi Password</label><input name='password' type='password'>";
  page += "<label>Laptop / Server IP</label><input name='server_ip' placeholder='192.168.1.10' required>";
  page += "<button type='submit'>Save and Restart</button></form>";
  page += "<p>Use the IP address of the laptop running the Flask server on port 5000.</p></main></body></html>";
  return page;
}

void startSetupPortal(const String &reason) {
  portalReason = reason;
  stopMotors();
  WiFi.persistent(false);
  WiFi.disconnect(false, true);
  delay(200);
  WiFi.mode(WIFI_AP);
  WiFi.softAP(SETUP_AP_SSID, SETUP_AP_PASSWORD);
  IPAddress apIP = WiFi.softAPIP();

  dnsServer.start(DNS_PORT, "*", apIP);

  setupServer.on("/", HTTP_GET, []() {
    setupServer.send(200, "text/html", setupPage(portalReason));
  });

  setupServer.on("/save", HTTP_POST, []() {
    String ssid = setupServer.arg("ssid");
    String password = setupServer.arg("password");
    String server = setupServer.arg("server_ip");
    ssid.trim();
    server.trim();

    if (!ssid.length() || !server.length()) {
      setupServer.send(400, "text/html", setupPage("SSID and server IP are required."));
      return;
    }

    prefs.begin("stasis_rover", false);
    prefs.putString("ssid", ssid);
    prefs.putString("password", password);
    prefs.putString("server", server);
    prefs.putString("build", FIRMWARE_BUILD_ID);
    prefs.end();

    setupServer.send(200, "text/html", "<html><body><h2>Saved. Restarting rover...</h2></body></html>");
    delay(1500);
    ESP.restart();
  });

  setupServer.onNotFound([]() {
    setupServer.send(200, "text/html", setupPage());
  });

  setupServer.begin();

  Serial.println();
  Serial.println("Rover setup portal started.");
  Serial.print("Connect to Wi-Fi: ");
  Serial.println(SETUP_AP_SSID);
  Serial.print("Password: ");
  Serial.println(SETUP_AP_PASSWORD);
  Serial.print("Open: http://");
  Serial.println(apIP);

  while (true) {
    dnsServer.processNextRequest();
    setupServer.handleClient();
    delay(2);
  }
}

bool loadSavedSettings(String &ssid, String &password, String &server) {
  prefs.begin("stasis_rover", true);
  ssid = prefs.getString("ssid", "");
  password = prefs.getString("password", "");
  server = prefs.getString("server", "");
  String savedBuild = prefs.getString("build", "");
  prefs.end();
  ssid.trim();
  server.trim();
  return ssid.length() > 0 && server.length() > 0 && savedBuild == FIRMWARE_BUILD_ID;
}

bool connectToWiFi(const String &ssid, const String &password) {
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid.c_str(), password.c_str());

  Serial.print("Connecting to WiFi: ");
  Serial.print(ssid);
  for (int i = 0; i < 60 && WiFi.status() != WL_CONNECTED; i++) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("WiFi connected, IP: ");
    Serial.println(WiFi.localIP());
    return true;
  }

  Serial.println("WiFi connection failed.");
  return false;
}

bool ensureNetworkSettings() {
  String ssid;
  String password;

  if (!loadSavedSettings(ssid, password, serverIp)) {
    startSetupPortal("No saved Wi-Fi/server settings found.");
  }

  if (!connectToWiFi(ssid, password)) {
    startSetupPortal("Could not connect with saved Wi-Fi settings. Enter new details.");
  }

  return true;
}

float normalizeAngle(float angle) {
  while (angle > 180.0) angle -= 360.0;
  while (angle < -180.0) angle += 360.0;
  return angle;
}

void writePwm(int pin, int value) {
  analogWrite(pin, constrain(value, 0, 255));
}

void setMotorA(int speed) {
  speed = constrain(speed, -255, 255);

  if (speed > 0) {
    digitalWrite(A_IA, HIGH);
    writePwm(A_IB, 255 - speed);
  } else if (speed < 0) {
    writePwm(A_IA, 255 + speed);
    digitalWrite(A_IB, HIGH);
  } else {
    digitalWrite(A_IA, LOW);
    digitalWrite(A_IB, LOW);
  }
}

void setMotorB(int speed) {
  speed = constrain(speed, -255, 255);

  if (speed > 0) {
    digitalWrite(B_IA, HIGH);
    writePwm(B_IB, 255 - speed);
  } else if (speed < 0) {
    writePwm(B_IA, 255 + speed);
    digitalWrite(B_IB, HIGH);
  } else {
    digitalWrite(B_IA, LOW);
    digitalWrite(B_IB, LOW);
  }
}

void stopMotors() {
  setMotorA(0);
  setMotorB(0);
}

void sendJson(const char *json) {
  if (webSocket.isConnected()) {
    webSocket.sendTXT(json);
  }
}

void sendHeartbeat() {
  sendJson("{\"status\":\"ready\"}");
}

void sendGoalReached() {
  sendJson("{\"status\":\"goal_reached\"}");
}

float readCompassHeading() {
  if (!compassReady) return yawDeg;

  sensors_event_t compassEvent;
  compass.getEvent(&compassEvent);

  float heading = atan2(compassEvent.magnetic.y, compassEvent.magnetic.x) * 180.0 / PI;
  if (heading < 0.0) heading += 360.0;
  return heading;
}

void sendTelemetry() {
  StaticJsonDocument<128> doc;
  doc["heading"] = readCompassHeading();
  doc["distance_traveled"] = distanceTraveledCm;

  char message[128];
  serializeJson(doc, message, sizeof(message));
  sendJson(message);
}

void sendTelemetryIfDue() {
  if (millis() - lastTelemetryMs < TELEMETRY_INTERVAL_MS) return;
  lastTelemetryMs = millis();
  sendTelemetry();
}

float getDistanceCm() {
  digitalWrite(ULTRASONIC_TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(ULTRASONIC_TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(ULTRASONIC_TRIG_PIN, LOW);

  unsigned long duration = pulseIn(ULTRASONIC_ECHO_PIN, HIGH, 30000);
  if (duration == 0) return -1.0;
  return duration * 0.0343 / 2.0;
}

void sendScanData() {
  StaticJsonDocument<512> doc;
  doc["type"] = "scan";
  JsonArray data = doc["data"].to<JsonArray>();

  for (int angle = 0; angle <= 180; angle += SCAN_STEP_DEG) {
    scannerServo.write(angle);
    delay(SCAN_SETTLE_MS);

    JsonObject point = data.add<JsonObject>();
    point["angle"] = angle;
    point["distance"] = getDistanceCm();

    webSocket.loop();
    updateYaw();
    sendTelemetryIfDue();
  }

  scannerServo.write(90);

  char message[512];
  serializeJson(doc, message, sizeof(message));
  sendJson(message);
}

void updateYaw() {
  if (!imuReady) return;

  sensors_event_t accel;
  sensors_event_t gyro;
  sensors_event_t temp;
  mpu.getEvent(&accel, &gyro, &temp);

  unsigned long now = millis();
  if (lastImuMs == 0) {
    lastImuMs = now;
    return;
  }

  float dt = (now - lastImuMs) / 1000.0;
  lastImuMs = now;

  float gyroZDegPerSec = (gyro.gyro.z * 180.0 / PI) - gyroZBias;
  if (fabs(gyroZDegPerSec) < 0.25) gyroZDegPerSec = 0.0;
  yawDeg = normalizeAngle(yawDeg + gyroZDegPerSec * dt);
}

void calibrateGyro() {
  const int samples = 300;
  float sum = 0.0;

  Serial.println("Calibrating gyro, keep rover still...");
  for (int i = 0; i < samples; i++) {
    sensors_event_t accel;
    sensors_event_t gyro;
    sensors_event_t temp;
    mpu.getEvent(&accel, &gyro, &temp);
    sum += gyro.gyro.z * 180.0 / PI;
    delay(5);
  }

  gyroZBias = sum / samples;
  yawDeg = 0.0;
  lastImuMs = millis();
  Serial.printf("Gyro Z bias: %.3f deg/s\n", gyroZBias);
}

void turnToAngle(float targetAngle) {
  if (!imuReady) {
    Serial.println("Cannot turn: MPU6050 is not ready");
    stopMotors();
    return;
  }

  unsigned long startMs = millis();

  while (millis() - startMs < 12000) {
    webSocket.loop();
    updateYaw();
    sendTelemetryIfDue();

    float error = normalizeAngle(targetAngle - readCompassHeading());
    if (fabs(error) <= TURN_TOLERANCE_DEG) break;

    int pwm = constrain((int)(fabs(error) * TURN_KP), TURN_MIN_PWM, TURN_MAX_PWM);
    if (error > 0) {
      setMotorA(pwm);
      setMotorB(-pwm);
    } else {
      setMotorA(-pwm);
      setMotorB(pwm);
    }

    delay(10);
  }

  stopMotors();
}

void driveForward(float distanceCm) {
  if (distanceCm < 0.0) distanceCm = 0.0;
  unsigned long driveTimeMs = (unsigned long)(distanceCm * DRIVE_MS_PER_CM);
  unsigned long startMs = millis();
  float startDistanceCm = distanceTraveledCm;

  while (millis() - startMs < driveTimeMs) {
    webSocket.loop();
    updateYaw();
    float progress = driveTimeMs > 0 ? (float)(millis() - startMs) / driveTimeMs : 1.0;
    distanceTraveledCm = startDistanceCm + distanceCm * constrain(progress, 0.0, 1.0);
    sendTelemetryIfDue();
    setMotorA(DRIVE_PWM);
    setMotorB(DRIVE_PWM);
    delay(10);
  }

  distanceTraveledCm = startDistanceCm + distanceCm;
  stopMotors();
}

void handleGoto(float angle, float distanceCm) {
  if (!imuReady) {
    stopMotors();
    sendJson("{\"status\":\"imu_error\"}");
    return;
  }

  turnToAngle(angle);
  delay(100);
  driveForward(distanceCm);
  sendGoalReached();
}

void handleCommand(const char *payload) {
  StaticJsonDocument<256> doc;
  DeserializationError err = deserializeJson(doc, payload);
  if (err) {
    Serial.println("Invalid JSON command");
    return;
  }

  const char *cmd = doc["cmd"] | "";
  if (strcmp(cmd, "goto") == 0) {
    handleGoto(doc["angle"] | 0.0, doc["distance"] | 0.0);
  } else if (strcmp(cmd, "scan") == 0) {
    sendScanData();
  }
}

void webSocketEvent(WStype_t type, uint8_t *payload, size_t length) {
  switch (type) {
    case WStype_CONNECTED:
      Serial.println("WebSocket connected");
      sendJson("{\"id\":\"esp32s3_rover\",\"type\":\"rover\"}");
      sendHeartbeat();
      break;

    case WStype_DISCONNECTED:
      Serial.println("WebSocket disconnected");
      stopMotors();
      break;

    case WStype_TEXT:
      {
        char message[256];
        size_t copyLen = length < sizeof(message) - 1 ? length : sizeof(message) - 1;
        memcpy(message, payload, copyLen);
        message[copyLen] = '\0';
        Serial.printf("Command: %s\n", message);
        handleCommand(message);
      }
      break;

    default:
      break;
  }
}

void setupMotors() {
  pinMode(A_IA, OUTPUT);
  pinMode(A_IB, OUTPUT);
  pinMode(B_IA, OUTPUT);
  pinMode(B_IB, OUTPUT);

  stopMotors();
}

void setupImu() {
  Wire.begin(SDA_PIN, SCL_PIN);
  if (!mpu.begin()) {
    Serial.println("MPU6050 not found");
    imuReady = false;
    return;
  }

  mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
  imuReady = true;
  calibrateGyro();
}

void setupCompass() {
  // GY-271/HMC5883L compass shares I2C with the MPU6050 at address 0x1E.
  if (!compass.begin()) {
    Serial.println("GY-271/HMC5883L compass not found");
    compassReady = false;
    return;
  }

  compassReady = true;
  Serial.println("GY-271/HMC5883L compass ready");
}

void setupScanner() {
  // HC-SR04 must be powered from 3.3V on this ESP32-S3 wiring.
  pinMode(ULTRASONIC_TRIG_PIN, OUTPUT);
  pinMode(ULTRASONIC_ECHO_PIN, INPUT);
  digitalWrite(ULTRASONIC_TRIG_PIN, LOW);

  scannerServo.setPeriodHertz(50);
  scannerServo.attach(SCANNER_SERVO_PIN, 500, 2400);
  scannerServo.write(90);
}

void setupWebSocket() {
  Serial.print("Connecting WebSocket to ws://");
  Serial.print(serverIp);
  Serial.println(":5000/ws/rover");
  webSocket.begin(serverIp.c_str(), SERVER_PORT, WEBSOCKET_PATH);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
  webSocket.enableHeartbeat(15000, 3000, 2);
}

void setup() {
  Serial.begin(115200);
  delay(1500);

  Serial.println();
  Serial.println("ESP32-S3 rover booting...");
  Serial.print("Firmware build: ");
  Serial.println(FIRMWARE_BUILD_ID);
  Serial.print("Reset reason: ");
  Serial.println((int)esp_reset_reason());
  Serial.flush();

  setupMotors();
  // Start Wi-Fi/config before sensor init so a bad sensor cannot block setup mode.
  ensureNetworkSettings();
  Serial.println("Network settings ready.");

  Serial.println("Starting IMU...");
  setupImu();
  Serial.println("Starting compass...");
  setupCompass();
  Serial.println("Starting ultrasonic scanner...");
  setupScanner();
  setupWebSocket();
}

void loop() {
  webSocket.loop();
  updateYaw();
  sendTelemetryIfDue();

  if (webSocket.isConnected() && millis() - lastHeartbeatMs >= 5000) {
    lastHeartbeatMs = millis();
    sendHeartbeat();
  }
}
