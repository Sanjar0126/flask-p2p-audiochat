import json
import threading
from typing import Dict, Any

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

    def handle_join(self, ws, room_id: str, data: dict):
        peer_id = data.get("peerId")
        if not peer_id:
            print("Invalid peerId in join message")
            return

        peer_name = data.get("peerName", peer_id)
        room = self.get_room(room_id)

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

    def handle_disconnect(self, room_id: str, data: dict):
        room = self.get_room(room_id)
        peer_id = data.get("peerId")
        
        if not peer_id:
            print("Invalid peerId in disconnect message")
            return

        with room.lock:
            room.peers.pop(peer_id, None)
            room.names.pop(peer_id, None)

            if not room.peers:
                with self.lock:
                    self.rooms.pop(room_id, None)
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

    def handle_offer(self, room_id: str, data: dict):
        room = self.get_room(room_id)
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

    def handle_answer(self, room_id: str, data: dict):
        room = self.get_room(room_id)
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

    def handle_ice_candidate(self, room_id: str, data: dict):
        room = self.get_room(room_id)
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
