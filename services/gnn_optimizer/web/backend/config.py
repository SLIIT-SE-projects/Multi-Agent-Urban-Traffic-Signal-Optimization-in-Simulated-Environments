import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'default_secret')
    PORT = int(os.getenv('PORT', 5001))
    HOST = os.getenv('HOST', '0.0.0.0')
    
    # Manager Service (Simulation)
    MANAGER_API = os.getenv('MANAGER_API', 'http://simulation-manager:5000/api')
    MANAGER_WS = os.getenv('MANAGER_WS', 'http://simulation-manager:5000')
