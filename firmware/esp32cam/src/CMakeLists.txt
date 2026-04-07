idf_component_register(
    SRCS "app_main.c" "human_detector.c" "stream_server.c" "uart_comms.c"
    INCLUDE_DIRS "."
    REQUIRES
        driver
        esp_wifi
        esp_http_server
        esp_event
        esp_timer
        nvs_flash
        esp_netif
        esp_camera
    PRIV_REQUIRES
        mbedtls
)
