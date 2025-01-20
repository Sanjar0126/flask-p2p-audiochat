# 
pip install -r requirements.txt

python start.py
or
gunicorn --bind 0.0.0.0:8080 -k gevent 'flaskr.app:create_app()'