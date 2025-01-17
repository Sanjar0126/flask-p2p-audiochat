from flask import Flask, request, jsonify, send_from_directory
from flask_sock import Sock
import json
from dataclasses import dataclass
from typing import Dict, Any
import threading
import os
import sys

app = Flask(__name__, static_folder='static')
sock = Sock(app)

app.config['SOCK_SERVER_OPTIONS'] = {'ping_interval': 25}

@dataclass
class PeerInfo:
    peer_id: str
    peer_name: str = None

class Room:
    def __init__(self):
        self.peers: Dict[str, Any] = {} 
        self.names: Dict[str, str] = {}  
        self.lock = threading.Lock()

class SignalingServer:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}
        self.lock = threading.Lock()

    def get_room(self, room_id: str) -> Room:
        with self.lock:
            if room_id not in self.rooms:
                self.rooms[room_id] = Room()
            return self.rooms[room_id]

server = SignalingServer()

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    return response

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_static(path):
    if not path:
        path = 'index.html'
    if not os.path.exists(os.path.join(app.static_folder, path)):
        path = 'index.html'
    return send_from_directory(app.static_folder, path)

@app.route('/rooms')
def get_rooms():
    return jsonify({"rooms": list(server.rooms.keys())})

@sock.route('/ws')
def handle_websocket(ws):
    print("New WebSocket connection established")
    try:
        while True:
            data = ws.receive()
            if not data:
                break
                
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                print(f"Invalid JSON received: {data}")
                continue

            event = message.get("event")
            data = message.get("data", {})
            room_id = message.get("room")

            if not all([event, room_id]):
                print("Missing required fields in message")
                continue

            print(f"Received event: {event} for room: {room_id}")

            if event == "join":
                handle_join(ws, room_id, data)
            elif event == "offer":
                handle_offer(room_id, data)
            elif event == "answer":
                handle_answer(room_id, data)
            elif event == "ice-candidate":
                handle_ice_candidate(room_id, data)
            elif event == "disconnect":
                handle_disconnect(room_id, data)

    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        print("WebSocket connection closed")

def handle_join(ws, room_id: str, data: dict):
    peer_id = data.get("peerId")
    if not peer_id:
        print("Invalid peerId in join message")
        return

    peer_name = data.get("peerName", peer_id)
    room = server.get_room(room_id)

    with room.lock:
        room.peers[peer_id] = ws
        room.names[peer_id] = peer_name

        existing_peers = [
            {"peerId": pid, "peerName": room.names[pid]}
            for pid in room.peers
            if pid != peer_id
        ]

        try:
            ws.send(json.dumps({
                "event": "peers-in-room",
                "data": {"peers": existing_peers},
                "room": room_id
            }))
        except Exception as e:
            print(f"Error sending peers-in-room message: {e}")
            return

        for pid, peer_ws in room.peers.items():
            if pid != peer_id:
                try:
                    peer_ws.send(json.dumps({
                        "event": "peer-joined",
                        "data": {
                            "peerId": peer_id,
                            "peerName": peer_name
                        },
                        "room": room_id
                    }))
                except Exception as e:
                    print(f"Error notifying peer {pid}: {e}")

def handle_disconnect(room_id: str, data: dict):
    room = server.get_room(room_id)
    peer_id = data.get("peerId")
    
    if not peer_id:
        print("Invalid peerId in disconnect message")
        return

    with room.lock:
        room.peers.pop(peer_id, None)
        room.names.pop(peer_id, None)

        if not room.peers:
            with server.lock:
                server.rooms.pop(room_id, None)
        else:
            for peer_ws in room.peers.values():
                try:
                    peer_ws.send(json.dumps({
                        "event": "peer-left",
                        "data": {"peerId": peer_id},
                        "room": room_id
                    }))
                except Exception as e:
                    print(f"Error notifying peer disconnect: {e}")

def handle_offer(room_id: str, data: dict):
    room = server.get_room(room_id)
    target = data.get("target")
    
    if not target:
        print("Invalid target in offer message")
        return

    with room.lock:
        if target in room.peers:
            try:
                room.peers[target].send(json.dumps({
                    "event": "offer",
                    "data": data,
                    "room": room_id
                }))
            except Exception as e:
                print(f"Error sending offer: {e}")

def handle_answer(room_id: str, data: dict):
    room = server.get_room(room_id)
    target = data.get("target")
    
    if not target:
        print("Invalid target in answer message")
        return

    with room.lock:
        if target in room.peers:
            try:
                room.peers[target].send(json.dumps({
                    "event": "answer",
                    "data": data,
                    "room": room_id
                }))
            except Exception as e:
                print(f"Error sending answer: {e}")

def handle_ice_candidate(room_id: str, data: dict):
    room = server.get_room(room_id)
    target = data.get("target")
    
    if not target:
        print("Invalid target in ICE candidate message")
        return

    with room.lock:
        if target in room.peers:
            try:
                room.peers[target].send(json.dumps({
                    "event": "ice-candidate",
                    "data": data,
                    "room": room_id
                }))
            except Exception as e:
                print(f"Error sending ICE candidate: {e}")

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"Server starting on port {port}")
    
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)