from flask import Flask, request, jsonify, send_from_directory
from flask_sock import Sock
import json
from dataclasses import dataclass
import os
import sys
from .ws_handlers import SignalingServer
import requests

from gevent.pywsgi import WSGIServer

@dataclass
class PeerInfo:
    peer_id: str
    peer_name: str = None

def create_app(test_config=None):
    app = Flask(__name__, static_folder='static')
    sock = Sock(app)
    signal_server = SignalingServer()

    app.config['SOCK_SERVER_OPTIONS'] = {'ping_interval': 25}
    
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
        # delay = 1
        # resp = requests.get(f'http://localhost:8000/?delay={delay}')

        rooms_data = {
            room_name: {
                "peers": list(room.peers.keys()), 
                "names": room.names  
            }
            for room_name, room in signal_server.rooms.items()
        }
        return jsonify({"rooms": rooms_data})

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
                    signal_server.handle_join(ws, room_id, data)
                elif event == "offer":
                    signal_server.handle_offer(room_id, data)
                elif event == "answer":
                    signal_server.handle_answer(room_id, data)
                elif event == "ice-candidate":
                    signal_server.handle_ice_candidate(room_id, data)
                elif event == "disconnect":
                    signal_server.handle_disconnect(room_id, data)

        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            print("WebSocket connection closed")
    
    return app

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"Server starting on port {port}")
    
    app = create_app()
    
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)