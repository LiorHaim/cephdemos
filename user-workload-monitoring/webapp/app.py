from flask import Flask
from flask import request, jsonify
import random 

app = Flask(__name__)

@app.route("/")
def home():
    return "Welcome to my exporter application! Nice to meet you!"
    
@app.route("/status", methods=["GET"])
def get_metrics():
    response = {} 
    response.update({'current_requests': random.randrange(0, 1000)})
    response.update({'pending_requests': random.randrange(0, 1000)})
    response.update({'total_uptime': random.randrange(0, 1000)})
    response.update({'health': random.choice(["healthy", "unhealthy"])})
    return jsonify(response)
    
if __name__ == "__main__":
    app.run(host='0.0.0.0', port='5000')
