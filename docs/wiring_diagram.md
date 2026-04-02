# STASIS — Wiring Diagram

## ESP32-S3 Pin Assignments

| Pin | Function | Connected To |
|-----|----------|-------------|
| GPIO4 | MOTOR_A_IN1 | L298N Channel 1 IN1 (Left Front) |
| GPIO5 | MOTOR_A_IN2 | L298N Channel 1 IN2 |
| GPIO6 | MOTOR_A_ENA | L298N Channel 1 ENA (PWM) |
| GPIO7 | MOTOR_B_IN1 | L298N Channel 2 IN3 (Left Rear) |
| GPIO8 | MOTOR_B_IN2 | L298N Channel 2 IN4 |
| GPIO9 | MOTOR_B_ENB | L298N Channel 2 ENB (PWM) |
| GPIO10 | MOTOR_C_IN1 | L298N Channel 3 IN1 (Right Front) |
| GPIO11 | MOTOR_C_IN2 | L298N Channel 3 IN2 |
| GPIO12 | MOTOR_C_ENA | L298N Channel 3 ENA (PWM) |
| GPIO13 | MOTOR_D_IN1 | L298N Channel 4 IN3 (Right Rear) |
| GPIO14 | MOTOR_D_IN2 | L298N Channel 4 IN4 |
| GPIO15 | MOTOR_D_ENB | L298N Channel 4 ENB (PWM) |
| GPIO16 | TEMP_SENSOR | DS18B20 Data (with 4.7kΩ pull-up) |
| GPIO17 | GPS_RX | NEO-6M TX |
| GPIO18 | GPS_TX | NEO-6M RX |
| GPIO19 | CAM_RX | ESP32-CAM TX (U0TXD) |
| GPIO20 | CAM_TX | ESP32-CAM RX (U0RXD) |
| GPIO21 | I2C_SDA | MPU6050 SDA + LCD SDA |
| GPIO22 | I2C_SCL | MPU6050 SCL + LCD SCL |
| GPIO2 | BUZZER | Passive Buzzer (+) |
| GPIO35 | BATTERY_ADC | Voltage divider midpoint |

## ESP32-CAM Pin Assignments (AI-Thinker)

Camera pins are fixed by the AI-Thinker PCB layout. UART uses default pins:
- **U0TXD** → ESP32-S3 GPIO19
- **U0RXD** → ESP32-S3 GPIO20
- **GPIO4** — Flash LED (software controlled)

## ESP32-C3 Mini Pin Assignments

| Pin | Function | Connected To |
|-----|----------|-------------|
| GPIO20 | PI_UART_RX | Raspberry Pi GPIO14 (TXD) |
| GPIO21 | PI_UART_TX | Raspberry Pi GPIO15 (RXD) |
| GPIO15 | CHARGING_RELAY | Relay module IN (HIGH = ON) |
| GPIO16 | EMERGENCY_STOP | Raspberry Pi GPIO input |

## Raspberry Pi Zero W

| Pin | Function | Connected To |
|-----|----------|-------------|
| GPIO14 (Pin 8) | TXD | ESP32-C3 GPIO20 (RX) |
| GPIO15 (Pin 10) | RXD | ESP32-C3 GPIO21 (TX) |
| GPIO18 | CHARGING_RELAY | Relay module (backup) |

## Power Wiring

- **Rover Battery** → Voltage regulator (5V) → ESP32-S3, ESP32-CAM, motors
- **Voltage Divider**: Battery+ → 100kΩ → ADC (GPIO35) → 100kΩ → GND
- **Motor Driver**: Separate motor power supply recommended (6-12V)
- **Charging Station**: USB power supply for Pi + separate relay-switched charger

## Notes

1. All I2C devices share the same bus (GPIO21/22) — ensure unique addresses
2. DS18B20 requires a 4.7kΩ pull-up resistor between Data and VCC
3. Level shifting may be needed between 3.3V ESP32 and 5V motor driver logic
4. Keep UART wires short and away from motor wires to avoid interference
