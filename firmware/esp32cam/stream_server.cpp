#include "stream_server.h"
#include "config.h"
#include <esp_camera.h>
#include <img_converters.h>
#include <WiFi.h>
#include <WebServer.h>

static WebServer _httpServer(STREAM_PORT);

static const char* STREAM_CONTENT_TYPE =
    "multipart/x-mixed-replace;boundary=stasisframe";
static const char* PART_BOUNDARY =
    "\r\n--stasisframe\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n";

static void _handleStream() {
    WiFiClient client = _httpServer.client();
    _httpServer.sendHeader("Cache-Control", "no-cache");
    _httpServer.sendHeader("Pragma", "no-cache");
    _httpServer.setContentLength(CONTENT_LENGTH_UNKNOWN);
    _httpServer.send(200, STREAM_CONTENT_TYPE, "");

    while (client.connected()) {
        camera_fb_t* fb = esp_camera_fb_get();
        if (!fb) continue;

        uint8_t* jpg_buf = NULL;
        size_t jpg_len = 0;
        bool converted = false;
        if (fb->format == PIXFORMAT_JPEG) {
            jpg_buf = fb->buf;
            jpg_len = fb->len;
        } else {
            converted = frame2jpg(fb, 80, &jpg_buf, &jpg_len);
        }

        if (jpg_buf && jpg_len > 0) {
            char hdr[80];
            int hdrLen = snprintf(hdr, sizeof(hdr), PART_BOUNDARY, jpg_len);
            client.write((uint8_t*)hdr, hdrLen);
            client.write(jpg_buf, jpg_len);
        }

        if (converted && jpg_buf) free(jpg_buf);
        esp_camera_fb_return(fb);

        if (!client.connected()) break;
        delay(STREAM_FPS_DELAY);
    }
}

static void _handleCapture() {
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) {
        _httpServer.send(500, "text/plain", "Camera capture failed");
        return;
    }

    uint8_t* jpg_buf = NULL;
    size_t jpg_len = 0;
    bool converted = false;
    if (fb->format == PIXFORMAT_JPEG) {
        jpg_buf = fb->buf;
        jpg_len = fb->len;
    } else {
        converted = frame2jpg(fb, 80, &jpg_buf, &jpg_len);
    }

    if (jpg_buf && jpg_len > 0) {
        _httpServer.sendHeader("Content-Type", "image/jpeg");
        _httpServer.sendHeader("Content-Length", String(jpg_len));
        _httpServer.send(200);
        WiFiClient client = _httpServer.client();
        client.write(jpg_buf, jpg_len);
    } else {
        _httpServer.send(500, "text/plain", "JPEG conversion failed");
    }

    if (converted && jpg_buf) free(jpg_buf);
    esp_camera_fb_return(fb);
}

static void _handleStatus() {
    String json = "{\"status\":\"online\",\"stream\":true,\"model\":\"AI-THINKER\"}";
    _httpServer.send(200, "application/json", json);
}

void startStreamServer() {
    _httpServer.on("/stream",  HTTP_GET, _handleStream);
    _httpServer.on("/capture", HTTP_GET, _handleCapture);
    _httpServer.on("/status",  HTTP_GET, _handleStatus);
    _httpServer.begin();
    Serial.printf("[STREAM] HTTP server on port %d\n", STREAM_PORT);
}

void handleStreamClients() {
    _httpServer.handleClient();
}