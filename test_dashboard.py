import time
import socketio

sio = socketio.Client()

@sio.event
def connect():
    print("[DASHBOARD] Connected to server!")
    # Wait a bit, then test controls
    time.sleep(2)
    print("[DASHBOARD] Emitting 'stop_rover'")
    sio.emit('stop_rover')
    time.sleep(1)
    
    for direction in ["forward", "back", "left", "right", "stop"]:
        print(f"[DASHBOARD] Emitting 'manual_move' {direction}")
        if direction == "stop":
            sio.emit('stop_rover')
        else:
            sio.emit('manual_move', {'direction': direction})
        time.sleep(1)
        
    sio.disconnect()

@sio.event
def disconnect():
    print("[DASHBOARD] Disconnected from server")

@sio.on('rover_status')
def on_rover_status(data):
    print(f"[DASHBOARD] Received rover_status: {data}")

@sio.on('camera_status')
def on_camera_status(data):
    print(f"[DASHBOARD] Received camera_status: {data}")

if __name__ == '__main__':
    print("[DASHBOARD] Connecting to http://127.0.0.1:5000 ...")
    sio.connect('http://127.0.0.1:5000')
    sio.wait()
