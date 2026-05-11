#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <ArduinoJson.h>
#include <WebSocketsClient.h>
#include <WiFi.h>
#include <Wire.h>

const char *WIFI_SSID = "YOUR_WIFI_SSID";
const char *WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

const char *SERVER_IP = "192.168.1.10";  // Update this to your laptop/server IP.
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
const float DRIVE_MS_PER_CM = 50.0;

Adafruit_MPU6050 mpu;
WebSocketsClient webSocket;

float yawDeg = 0.0;
float gyroZBias = 0.0;
unsigned long lastImuMs = 0;
unsigned long lastHeartbeatMs = 0;
bool imuReady = false;

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
  if (webSocket.isConnected()) webSocket.sendTXT(json);
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

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.print("WiFi connected, IP: ");
  Serial.println(WiFi.localIP());
}

void setupWebSocket() {
  webSocket.begin(SERVER_IP, SERVER_PORT, WEBSOCKET_PATH);
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
  connectWiFi();
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
