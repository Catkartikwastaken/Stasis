======================================================================
   ███████╗████████╗ █████╗ ███████╗██╗███████╗
   ██╔════╝╚══██╔══╝██╔══██╗██╔════╝██║██╔════╝
   ███████╗   ██║   ███████║███████╗██║███████╗
   ╚════██║   ██║   ██╔══██║╚════██║██║╚════██║
   ███████║   ██║   ██║  ██║███████║██║███████║
   ╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝╚══════╝

        Autonomous Forest Patrol Rover System
======================================================================

STASIS is a self-contained autonomous rover system designed to patrol
geofenced areas, detect human presence, and report activity in real
time. It operates entirely on a local network without relying on any
external cloud infrastructure.

The system combines embedded firmware, a local backend server, and a
web-based dashboard to provide a complete monitoring and control
solution. It is intended for use in environments such as forests,
restricted zones, or private land where continuous automated patrol is
required.

----------------------------------------------------------------------
OVERVIEW
----------------------------------------------------------------------

The STASIS system is composed of three primary components:

1. Rover Unit (ESP32-S3 + ESP32-CAM)
   Handles movement, sensing, navigation, and human detection.

2. Charging Station (Raspberry Pi Zero W + ESP32-C3)
   Acts as the system controller, communication bridge, and server host.

3. Web Dashboard
   Provides a user interface for monitoring telemetry, viewing alerts,
   and controlling rover behavior.

The rover operates autonomously within a defined GPS boundary,
continuously monitoring its surroundings and reporting events back to
the station.

----------------------------------------------------------------------
CORE CAPABILITIES
----------------------------------------------------------------------

- GPS-based geofencing using polygon boundaries
- Autonomous patrol with path learning and reuse
- Human detection using motion analysis and ML confirmation
- Real-time telemetry streaming (location, battery, sensors)
- Automatic return to charging station on low battery
- Local alert system with image capture
- Web-based control interface with live map and camera feed
- Daily report generation with patrol summaries
- Fully local deployment without cloud dependency

----------------------------------------------------------------------
SYSTEM ARCHITECTURE
----------------------------------------------------------------------

   [ Rover (ESP32-S3 + CAM) ]
               |
         ESP-NOW / BLE
               |
   [ ESP32-C3 WiFi Bridge ]
               |
             UART
               |
   [ Raspberry Pi Server ]
               |
        HTTP / WebSocket
               |
        [ Web Dashboard ]

----------------------------------------------------------------------
HARDWARE REQUIREMENTS
----------------------------------------------------------------------

Component                     Quantity   Purpose
--------------------------------------------------------------
ESP32-S3                      1          Main rover controller
ESP32-CAM                     1          Camera and detection
ESP32-C3 Mini                 1          WiFi bridge and relay
Raspberry Pi Zero W           1          Backend server
Motor driver (L298N/L293D)    1          Motor control
DC motors                     4          Movement
NEO-6M GPS module             1          Position tracking
MPU6050                       1          Motion and tilt sensing
DS18B20                       1          Temperature monitoring
I2C LCD                       1          Status display
Battery pack                  1          Power source
Charging dock components      1          Charging system

----------------------------------------------------------------------
QUICK START
----------------------------------------------------------------------

1. Flash firmware to all ESP32 boards
   - ESP32-S3 (rover control)
   - ESP32-CAM (camera + detection)
   - ESP32-C3 (WiFi bridge)

2. Set up Raspberry Pi
   - Install Node.js 18+
   - Clone repository
   - Install dependencies

3. Start backend server
   - Configure environment variables
   - Run server process

4. Build and deploy dashboard
   - Build React app
   - Serve via backend

5. Connect to network
   - Join STASIS WiFi network or configured LAN

6. Open dashboard in browser
   - Monitor rover
   - Configure geofence
   - Begin patrol

----------------------------------------------------------------------
PROJECT STRUCTURE
----------------------------------------------------------------------

stasis-rover/
├── firmware/
│   ├── esp32s3/
│   ├── esp32cam/
│   └── esp32c3/
├── server/
├── dashboard/
├── docs/
├── scripts/
└── hardware/

----------------------------------------------------------------------
DASHBOARD FUNCTIONALITY
----------------------------------------------------------------------

The web dashboard provides:

- Live rover status (battery, temperature, state)
- Interactive map with rover position and geofence
- Real-time telemetry charts
- Camera stream and captured snapshots
- Alert history with filtering and acknowledgement
- Command interface for manual control
- System configuration settings

----------------------------------------------------------------------
DATA STORAGE
----------------------------------------------------------------------

All system data is stored locally using SQLite:

- Telemetry logs
- Alert records with images
- Geofence configurations
- Learned navigation paths
- Daily patrol reports

No external services or cloud storage are used.

----------------------------------------------------------------------
REPORT GENERATION
----------------------------------------------------------------------

A daily report is automatically generated containing:

- Patrol distance and duration
- State distribution (idle, patrol, charging)
- Detection events with timestamps and locations
- Temperature statistics
- Battery usage patterns
- Movement trace visualization

Reports are saved locally and can be downloaded via the dashboard.

----------------------------------------------------------------------
SAFETY AND FAILSAFE BEHAVIOR
----------------------------------------------------------------------

The rover includes built-in safeguards:

- Automatic stop on tilt or obstruction detection
- Low battery return protocol
- Communication watchdog monitoring
- Manual override commands from dashboard
- Emergency stop capability

----------------------------------------------------------------------
DEVELOPMENT NOTES
----------------------------------------------------------------------

- Firmware uses Arduino framework for ESP32
- Backend uses Node.js with Express and Socket.IO
- Frontend uses React with Vite and Tailwind
- Communication is handled via ESP-NOW and UART bridging

The system is modular. Each subsystem can be modified or extended
independently.

----------------------------------------------------------------------
CONTRIBUTING
----------------------------------------------------------------------

Refer to CONTRIBUTING.md for guidelines on:

- Code structure
- Commit standards
- Testing expectations
- Pull request process

----------------------------------------------------------------------
LICENSE
----------------------------------------------------------------------

This project is licensed under the MIT License.

----------------------------------------------------------------------
FOOTER
----------------------------------------------------------------------

Built as a fully local autonomous monitoring system with an emphasis
on reliability, simplicity, and control."# Stasis" 
