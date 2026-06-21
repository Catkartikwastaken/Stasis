/**
 * @file stasis_motor_controller.ino
 * @brief ESP32-S3 Motor Controller for STASIS Forest Monitoring Rover
 * 
 * This firmware runs on an ESP32-S3 microcontroller. Its sole responsibility is 
 * to receive serial motor speed commands (left and right channel) from a host device 
 * (e.g., a Raspberry Pi) and drive an L911S dual-channel H-bridge motor driver.
 * 
 * Communication Protocol:
 * - Baud Rate: 115200 baud
 * - Command format: "M:left_speed,right_speed\n"
 *   - 'M' is the command prefix.
 *   - 'left_speed' and 'right_speed' are integers in the range [-100, 100].
 *   - Example: "M:80,-80\n" (Left forward 80%, Right reverse 80%)
 *   - Example: "M:0,0\n" (Stop both motors)
 * 
 * Safety Features:
 * - Failsafe Timeout: If no valid command is received within 2000 milliseconds,
 *   the controller will automatically stop all motors to prevent a runaway condition.
 * 
 * L911S H-Bridge Driver Logic:
 * - Left Motor:
 *   - Forward: Pin A-IA = PWM, Pin A-IB = LOW
 *   - Reverse: Pin A-IA = LOW, Pin A-IB = PWM
 *   - Stop:    Pin A-IA = LOW, Pin A-IB = LOW
 * - Right Motor:
 *   - Forward: Pin B-IA = PWM, Pin B-IB = LOW
 *   - Reverse: Pin B-IA = LOW, Pin B-IB = PWM
 *   - Stop:    Pin B-IA = LOW, Pin B-IB = LOW
 */

#include <Arduino.h>

// ==========================================
// CONFIGURATION & PIN DEFINITIONS
// ==========================================

// ESP32-S3 GPIO Pins connected to the L911S driver.
// Adjust these pins according to your physical wiring.
#define PIN_LEFT_MOTOR_IA  4   // Left Motor Input A (Forward Control)
#define PIN_LEFT_MOTOR_IB  5   // Left Motor Input B (Reverse Control)
#define PIN_RIGHT_MOTOR_IA 6   // Right Motor Input A (Forward Control)
#define PIN_RIGHT_MOTOR_IB 7   // Right Motor Input B (Reverse Control)

// Serial Communication Settings
#define SERIAL_BAUD_RATE   115200
#define SERIAL_TIMEOUT_MS  50

// Safety Failsafe Settings
#define FAILSAFE_TIMEOUT_MS 2000 // Stop motors if no serial message for 2 seconds

// PWM Configuration
#define PWM_FREQ           1000  // 1 kHz frequency (standard for DC motors)
#define PWM_RESOLUTION     8     // 8-bit resolution (0-255 duty cycle)

// ==========================================
// STATE VARIABLES
// ==========================================
unsigned long lastCommandTime = 0; // Tracks the last time a valid command was received
bool failsafeTriggered = false;    // Safety state flag

// ==========================================
// FUNCTION PROTOTYPES
// ==========================================
void setupMotors();
void setMotorSpeeds(int leftSpeed, int rightSpeed);
void processSerialInput();
void handleFailsafe();
void writePWM(uint8_t pin, int dutyCycle);

/**
 * @brief Initialize hardware interfaces.
 */
void setup() {
  // Initialize Serial interface
  Serial.begin(SERIAL_BAUD_RATE);
  Serial.setTimeout(SERIAL_TIMEOUT_MS);
  
  // Wait briefly for serial to stabilize (useful for ESP32-S3 USB OTG)
  delay(500);
  Serial.println("\n--- STASIS ESP32-S3 Motor Controller Initialized ---");
  Serial.println("Protocol: M:left,right\\n (Speeds from -100 to 100)");

  // Initialize GPIO pins for motor driving
  setupMotors();
  
  // Initialize the failsafe timer
  lastCommandTime = millis();
}

/**
 * @brief Main execution loop.
 */
void loop() {
  // 1. Check for incoming serial commands and process them
  processSerialInput();
  
  // 2. Validate failsafe condition
  handleFailsafe();
}

/**
 * @brief Configure GPIO motor pins.
 * 
 * Supports both older and newer ESP32 core versions using native PWM methods.
 */
void setupMotors() {
  pinMode(PIN_LEFT_MOTOR_IA, OUTPUT);
  pinMode(PIN_LEFT_MOTOR_IB, OUTPUT);
  pinMode(PIN_RIGHT_MOTOR_IA, OUTPUT);
  pinMode(PIN_RIGHT_MOTOR_IB, OUTPUT);
  
  // Ensure all pins start at LOW (motors stopped)
  digitalWrite(PIN_LEFT_MOTOR_IA, LOW);
  digitalWrite(PIN_LEFT_MOTOR_IB, LOW);
  digitalWrite(PIN_RIGHT_MOTOR_IA, LOW);
  digitalWrite(PIN_RIGHT_MOTOR_IB, LOW);

#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  // ESP32 Arduino Core 3.0.0+ uses ledcAttach and ledcWrite
  ledcAttach(PIN_LEFT_MOTOR_IA, PWM_FREQ, PWM_RESOLUTION);
  ledcAttach(PIN_LEFT_MOTOR_IB, PWM_FREQ, PWM_RESOLUTION);
  ledcAttach(PIN_RIGHT_MOTOR_IA, PWM_FREQ, PWM_RESOLUTION);
  ledcAttach(PIN_RIGHT_MOTOR_IB, PWM_FREQ, PWM_RESOLUTION);
#else
  // Older ESP32 cores (2.x) support analogWrite natively for PWM pin control.
  // We can write directly using analogWrite on ESP32 pins.
#endif
  
  Serial.println("Motor driver GPIO pins configured successfully.");
}

/**
 * @brief Safe analog/PWM output driver helper.
 * 
 * Handles core-independent duty writing.
 * 
 * @param pin The GPIO pin target
 * @param dutyCycle The 8-bit duty cycle value (0 to 255)
 */
void writePWM(uint8_t pin, int dutyCycle) {
  dutyCycle = constrain(dutyCycle, 0, 255);
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(pin, dutyCycle);
#else
  analogWrite(pin, dutyCycle);
#endif
}

/**
 * @brief Drive the L911S motor pins given left and right speed percentages.
 * 
 * @param leftSpeed Left motor speed (-100 to 100)
 * @param rightSpeed Right motor speed (-100 to 100)
 */
void setMotorSpeeds(int leftSpeed, int rightSpeed) {
  // Constrain inputs to legal ranges [-100, 100]
  leftSpeed = constrain(leftSpeed, -100, 100);
  rightSpeed = constrain(rightSpeed, -100, 100);

  // Convert speed percentage (0-100) to 8-bit PWM value (0-255)
  int leftPwm = map(abs(leftSpeed), 0, 100, 0, 255);
  int rightPwm = map(abs(rightSpeed), 0, 100, 0, 255);

  // --- Left Motor Direction Control ---
  if (leftSpeed > 0) {
    // Drive Left Forward
    writePWM(PIN_LEFT_MOTOR_IA, leftPwm);
    writePWM(PIN_LEFT_MOTOR_IB, 0);
  } else if (leftSpeed < 0) {
    // Drive Left Reverse
    writePWM(PIN_LEFT_MOTOR_IA, 0);
    writePWM(PIN_LEFT_MOTOR_IB, leftPwm);
  } else {
    // Stop Left Motor
    writePWM(PIN_LEFT_MOTOR_IA, 0);
    writePWM(PIN_LEFT_MOTOR_IB, 0);
  }

  // --- Right Motor Direction Control ---
  if (rightSpeed > 0) {
    // Drive Right Forward
    writePWM(PIN_RIGHT_MOTOR_IA, rightPwm);
    writePWM(PIN_RIGHT_MOTOR_IB, 0);
  } else if (rightSpeed < 0) {
    // Drive Right Reverse
    writePWM(PIN_RIGHT_MOTOR_IA, 0);
    writePWM(PIN_RIGHT_MOTOR_IB, rightPwm);
  } else {
    // Stop Right Motor
    writePWM(PIN_RIGHT_MOTOR_IA, 0);
    writePWM(PIN_RIGHT_MOTOR_IB, 0);
  }
}

/**
 * @brief Reads, buffers, and parses incoming Serial data.
 * 
 * Listens for commands like "M:left,right\n" and routes parsed speeds.
 */
void processSerialInput() {
  static String inputBuffer = ""; // Static buffer to preserve data across loops

  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    
    // Check for packet terminator
    if (c == '\n' || c == '\r') {
      if (inputBuffer.length() > 0) {
        inputBuffer.trim(); // Strip extraneous whitespace
        
        // Ensure packet matches basic protocol: starts with 'M' or 'm' and has ':'
        if ((inputBuffer.startsWith("M") || inputBuffer.startsWith("m")) && inputBuffer.indexOf(':') != -1) {
          int colonIdx = inputBuffer.indexOf(':');
          String speedData = inputBuffer.substring(colonIdx + 1);
          int commaIdx = speedData.indexOf(',');
          
          if (commaIdx != -1) {
            String leftStr = speedData.substring(0, commaIdx);
            String rightStr = speedData.substring(commaIdx + 1);
            
            leftStr.trim();
            rightStr.trim();

            int leftSpeed = leftStr.toInt();
            int rightSpeed = rightStr.toInt();

            // Set motor speeds immediately
            setMotorSpeeds(leftSpeed, rightSpeed);
            
            // Refresh failsafe timestamp
            lastCommandTime = millis();
            if (failsafeTriggered) {
              failsafeTriggered = false;
              Serial.println("INFO: Communication restored. Failsafe inactive.");
            }
            
            // Acknowledge receipt back to the Raspberry Pi
            Serial.printf("ACK:%d,%d\n", leftSpeed, rightSpeed);
          } else {
            Serial.println("ERR: Malformed speed arguments. Missing comma separator.");
          }
        } else {
          Serial.printf("ERR: Unknown command prefix in string: '%s'\n", inputBuffer.c_str());
        }
        inputBuffer = ""; // Reset buffer after processing command packet
      }
    } else {
      // Append character to the processing buffer if length constraints allow
      if (inputBuffer.length() < 64) {
        inputBuffer += c;
      } else {
        // Prevent buffer overflows from noise
        inputBuffer = "";
        Serial.println("ERR: Serial receive buffer overflow.");
      }
    }
  }
}

/**
 * @brief Implements the timeout failsafe safety protocol.
 * 
 * Halts motors if no telemetry activity has occurred in FAILSAFE_TIMEOUT_MS.
 */
void handleFailsafe() {
  unsigned long now = millis();
  
  if (now - lastCommandTime > FAILSAFE_TIMEOUT_MS) {
    if (!failsafeTriggered) {
      // Stop both motors instantly for safety
      setMotorSpeeds(0, 0);
      failsafeTriggered = true;
      Serial.println("WARNING: Failsafe triggered! Serial communication lost. Motors stopped.");
    }
    // Constantly refresh command timestamp to prevent rollover overflow glitches, 
    // but keep failsafe flag active.
    lastCommandTime = now - (FAILSAFE_TIMEOUT_MS + 10);
  }
}
