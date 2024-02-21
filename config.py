import dotenv

# Load environment variables
dotenv.load_dotenv(".env")

# Configuration variables
URL = dotenv.get_key(".env", "url")
DB = dotenv.get_key(".env", "db")
USERNAME = dotenv.get_key(".env", "username")
API_KEY = dotenv.get_key(".env", "api_key")