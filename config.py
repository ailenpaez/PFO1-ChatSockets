from pathlib import Path

# config servidor

HOST = "127.0.0.1"
PORT = 5000

BUFFER_SIZE = 1024  # maximo bytes x mensaje 


# Config BBDD

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"

DB_PATH = DATA_DIR / "chat.db"