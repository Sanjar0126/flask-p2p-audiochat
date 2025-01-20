import sys
from flaskr.app import create_app

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"Server starting on port {port}")
    
    app = create_app()
    
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)