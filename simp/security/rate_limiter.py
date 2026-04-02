from flask import Flask, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
# Create a Limiter instance with default key function set to get_remote_address
limiter = Limiter(get_remote_address)

@limiter.limit("10/minute", path="/intents/route")
def intents_route():
    return "Intents route"  # Placeholder response

@limiter.limit("5/minute", path="/agents/register")
def agents_register():
    return "Agents registration"  # Placeholder response

@limiter.limit("1/minute", path="/control")
def control():
    return "Control endpoint"  # Placeholder response

if __name__ == '__main__':
    app.run()