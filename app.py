from flask import Flask
from init import api

def create_app():
    app = Flask(__name__)
    api.init_app(app)
    
    from routes import tickets_ns 
    
    api.add_namespace(tickets_ns)
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
