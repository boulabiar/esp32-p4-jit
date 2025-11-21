idf_component_register(SRCS "main.c" "usb_transport.c" "protocol.c" "commands.c"
                    INCLUDE_DIRS "."
                    REQUIRES tinyusb esp_mm)
