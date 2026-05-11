#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <ArduinoJson.h>
#include <DNSServer.h>
#include <Preferences.h>
#include <WebServer.h>
#include <WebSocketsClient.h>
#include <WiFi.h>
#include <Wire.h>
#include <math.h>
#include <string.h>

const char *SETUP_AP_SSID = "STASIS-ROVER-SETUP";
const char *SETUP_AP_PASSWORD = "stasis1234";

const uint16_t SERVER_PORT = 5000;
const char *WEBSOCKET_PATH = "/ws/rover";

const int A_IA = 26;
const int A_IB = 27;
const int B_IA = 14;
const int B_IB = 12;
const int BUZZER_PIN = 33;
const int SDA_PIN = 21;
const int SCL_PIN = 22;

const float TURN_KP = 5.0;
const float TURN_TOLERANCE_DEG = 5.0;
const int TURN_MIN_PWM = 75;
const int TURN_MAX_PWM = 200;
const int DRIVE_PWM = 180;
const float DRIVE_MS_PER_CM = 50.0;  // Tune this on the real floor.

const byte DNS_PORT = 53;

Adafruit_MPU6050 mpu;
DNSServer dnsServer;
Preferences prefs;
WebServer setupServer(80);
WebSocketsClient webSocket;

String serverIp = "";
String portalReason = "";
float yawDeg = 0.0;
float gyroZBias = 0.0;
unsigned long lastImuMs = 0;
unsigned long lastHeartbeatMs = 0;
bool imuReady = false;

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
  WiFi.disconnect(true);
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
  prefs.end();
  ssid.trim();
  server.trim();
  return ssid.length() > 0 && server.length() > 0;
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

    float error = normalizeAngle(targetAngle - yawDeg);
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

  while (millis() - startMs < driveTimeMs) {
    webSocket.loop();
    updateYaw();
    setMotorA(DRIVE_PWM);
    setMotorB(DRIVE_PWM);
    delay(10);
  }

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

void soundBuzzer() {
  digitalWrite(BUZZER_PIN, HIGH);
  delay(1000);
  digitalWrite(BUZZER_PIN, LOW);
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
  } else if (strcmp(cmd, "alert_buzzer") == 0) {
    soundBuzzer();
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
  delay(500);

  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  setupMotors();
  setupImu();
  ensureNetworkSettings();
  setupWebSocket();
}

void loop() {
  webSocket.loop();
  updateYaw();

  if (webSocket.isConnected() && millis() - lastHeartbeatMs >= 5000) {
    lastHeartbeatMs = millis();
    sendHeartbeat();
  }
}
