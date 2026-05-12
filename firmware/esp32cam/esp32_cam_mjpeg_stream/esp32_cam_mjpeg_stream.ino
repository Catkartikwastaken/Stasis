#include "esp_camera.h"
#include "esp_http_server.h"
#include <DNSServer.h>
#include <Preferences.h>
#include <WebServer.h>
#include <WiFi.h>
#include <string.h>

const char *SETUP_AP_SSID = "STASIS-CAM-SETUP";
const char *SETUP_AP_PASSWORD = "stasis1234";
const char *FIRMWARE_BUILD_ID = __DATE__ " " __TIME__;

// AI-Thinker ESP32-CAM pin map
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

const byte DNS_PORT = 53;

DNSServer dnsServer;
Preferences prefs;
WebServer setupServer(80);
httpd_handle_t stream_httpd = NULL;
String portalReason = "";

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
  page += "<title>STASIS Camera Setup</title><style>";
  page += "body{font-family:Arial,sans-serif;background:#111827;color:#f9fafb;margin:0;padding:24px}";
  page += "main{max-width:420px;margin:0 auto;background:#1f2937;border:1px solid #374151;border-radius:8px;padding:18px}";
  page += "label{display:block;margin:14px 0 6px}input{width:100%;padding:10px;border-radius:6px;border:1px solid #4b5563;background:#111827;color:#fff}";
  page += "button{margin-top:18px;width:100%;padding:12px;border:0;border-radius:6px;background:#2563eb;color:#fff;font-weight:bold}";
  page += ".msg{color:#fbbf24}</style></head><body><main><h2>STASIS Camera Setup</h2>";
  if (message.length()) page += "<p class='msg'>" + htmlEscape(message) + "</p>";
  page += "<form method='POST' action='/save'>";
  page += "<label>Wi-Fi SSID</label><input name='ssid' required autocomplete='off'>";
  page += "<label>Wi-Fi Password</label><input name='password' type='password'>";
  page += "<button type='submit'>Save and Restart</button></form>";
  page += "<p>After restart, check Serial Monitor for the camera stream IP.</p></main></body></html>";
  return page;
}

void startSetupPortal(const String &reason) {
  portalReason = reason;
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
    ssid.trim();

    if (!ssid.length()) {
      setupServer.send(400, "text/html", setupPage("SSID cannot be empty."));
      return;
    }

    prefs.begin("stasis_cam", false);
    prefs.putString("ssid", ssid);
    prefs.putString("password", password);
    prefs.putString("build", FIRMWARE_BUILD_ID);
    prefs.end();

    setupServer.send(200, "text/html", "<html><body><h2>Saved. Restarting camera...</h2></body></html>");
    delay(1500);
    ESP.restart();
  });

  setupServer.onNotFound([]() {
    setupServer.send(200, "text/html", setupPage());
  });

  setupServer.begin();

  Serial.println();
  Serial.println("Camera setup portal started.");
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

bool loadSavedWiFi(String &ssid, String &password) {
  prefs.begin("stasis_cam", true);
  ssid = prefs.getString("ssid", "");
  password = prefs.getString("password", "");
  String savedBuild = prefs.getString("build", "");
  prefs.end();
  ssid.trim();
  return ssid.length() > 0 && savedBuild == FIRMWARE_BUILD_ID;
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

bool ensureWiFi() {
  String ssid;
  String password;

  if (!loadSavedWiFi(ssid, password)) {
    startSetupPortal("No saved Wi-Fi settings found.");
  }

  if (!connectToWiFi(ssid, password)) {
    startSetupPortal("Could not connect with saved Wi-Fi settings. Enter new details.");
  }

  return true;
}

static esp_err_t stream_handler(httpd_req_t *req) {
  static const char *STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=frame";
  static const char *STREAM_BOUNDARY = "--frame\r\n";
  static const char *STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

  char part_buf[64];
  esp_err_t res = httpd_resp_set_type(req, STREAM_CONTENT_TYPE);
  if (res != ESP_OK) return res;

  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

  while (true) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Camera capture failed");
      return ESP_FAIL;
    }

    size_t header_len = snprintf(part_buf, sizeof(part_buf), STREAM_PART, fb->len);
    res = httpd_resp_send_chunk(req, STREAM_BOUNDARY, strlen(STREAM_BOUNDARY));
    if (res == ESP_OK) res = httpd_resp_send_chunk(req, part_buf, header_len);
    if (res == ESP_OK) res = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
    if (res == ESP_OK) res = httpd_resp_send_chunk(req, "\r\n", 2);

    esp_camera_fb_return(fb);

    if (res != ESP_OK) {
      break;
    }
  }

  return res;
}

void startCameraServer() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 80;

  httpd_uri_t stream_uri = {};
  stream_uri.uri = "/stream";
  stream_uri.method = HTTP_GET;
  stream_uri.handler = stream_handler;
  stream_uri.user_ctx = NULL;

  if (httpd_start(&stream_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(stream_httpd, &stream_uri);
  }
}

bool initCamera() {
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
  config.frame_size = FRAMESIZE_QVGA;
  config.jpeg_quality = 12;
  config.fb_count = psramFound() ? 2 : 1;
  config.fb_location = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
  config.grab_mode = CAMERA_GRAB_LATEST;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed: 0x%x\n", err);
    return false;
  }

  return true;
}

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(false);
  delay(1000);

  WiFi.mode(WIFI_STA);
  Serial.println();
  Serial.println("ESP32-CAM booting...");
  Serial.print("Firmware build: ");
  Serial.println(FIRMWARE_BUILD_ID);
  Serial.print("ESP32-CAM MAC: ");
  Serial.println(WiFi.macAddress());

  ensureWiFi();

  if (!initCamera()) {
    return;
  }

  startCameraServer();

  Serial.print("Camera stream ready: http://");
  Serial.print(WiFi.localIP());
  Serial.println("/stream");
}

void loop() {
  delay(10000);
}
