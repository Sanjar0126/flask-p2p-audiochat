from gevent.pywsgi import WSGIServer
from flaskr.app import create_app
from gevent import monkey
monkey.patch_all()

app = create_app()
http_server = WSGIServer(("0.0.0.0", 8080), app)
# http_server.set_spawn = 4
http_server.serve_forever()
