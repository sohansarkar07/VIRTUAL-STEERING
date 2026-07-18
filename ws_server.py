"""
Virtual Steering — WebSocket Bridge Server
==========================================
Connects the browser-based hand tracking app to real OS keyboard inputs.

Browser sends gesture commands → this server → pynput → any game gets keys.

Usage:
    python ws_server.py

Then open the web app and it will connect automatically.
"""
import asyncio
import json
import os
os.environ.setdefault("GLOG_minloglevel", "3")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

try:
    import websockets
except ImportError:
    print("[ERROR] websockets not installed. Run:  pip install websockets")
    raise

from pynput.keyboard import Controller, Key

keyboard  = Controller()

# Map of action name → key to press
KEY_MAP = {
    "left"  : Key.left,
    "right" : Key.right,
    "gas"   : Key.up,
    "brake" : Key.down,
}

# Currently pressed keys (to avoid repeated presses)
pressed: set = set()


def press_key(action: str):
    key = KEY_MAP.get(action)
    if key and action not in pressed:
        keyboard.press(key)
        pressed.add(action)


def release_key(action: str):
    key = KEY_MAP.get(action)
    if key and action in pressed:
        keyboard.release(key)
        pressed.discard(action)


def release_all():
    for action in list(pressed):
        release_key(action)


async def handle(websocket):
    print(f"[WS]  Browser connected from {websocket.remote_address}")
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                # Expected format:
                #   { "type": "press",   "key": "gas"   }
                #   { "type": "release", "key": "left"  }
                #   { "type": "release_all" }
                t = data.get("type")
                k = data.get("key", "")

                if t == "press":
                    press_key(k)
                elif t == "release":
                    release_key(k)
                elif t == "release_all":
                    release_all()

            except (json.JSONDecodeError, KeyError):
                pass

    except websockets.exceptions.ConnectionClosed:
        print("[WS]  Browser disconnected — releasing all keys")
        release_all()


async def main():
    host = "localhost"
    port = 8765
    print(f"[WS]  Virtual Steering bridge running on ws://{host}:{port}")
    print(f"[WS]  Open the web app — it will connect automatically.")
    print(f"[WS]  Focus any game window, then use gestures to control it!")
    print(f"[WS]  Press Ctrl+C to stop.\n")

    async with websockets.serve(handle, host, port):
        await asyncio.Future()   # run forever


if __name__ == "__main__":
    asyncio.run(main())
