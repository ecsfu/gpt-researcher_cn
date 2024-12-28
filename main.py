from dotenv import load_dotenv
import os
os.environ["https_proxy"] = 'http://127.0.0.1:7890'
load_dotenv()

from backend.server.server import app

if __name__ == "__main__":
    import uvicorn


    port = 8012
    print(port)
    uvicorn.run(app, host="0.0.0.0", port=port)
