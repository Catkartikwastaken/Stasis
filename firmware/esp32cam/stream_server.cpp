#include "stream_server.h"
#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>

WebServer server(81);

void handleJPG() {
    camera_fb_t * fb = esp_camera_fb_get();
    if (!fb) {
        server.send(500, "text/plain", "Camera capture failed");
        return;
    }

    server.sendHeader("Content-Type", "image/jpeg");
    server.sendHeader("Content-Length", String(fb->len));
    server.send(200);

    WiFiClient client = server.client();
    client.write(fb->buf, fb->len);

    esp_camera_fb_return(fb);
}

void startCameraServer() {
    server.on("/capture", HTTP_GET, handleJPG);
    server.begin();
}

void handleClient() {
    server.handleClient();
}