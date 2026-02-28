import os
from app import create_app, Config

app = create_app(Config)

if __name__ == "__main__":
    host = os.environ.get("CAMPUS_PULSE_HOST", "127.0.0.1")
    port = int(os.environ.get("CAMPUS_PULSE_PORT", "5000"))
    app.run(host=host, port=port)
