import os
from flask import Flask, request

app = Flask(__name__)

@app.route("/process")
def process():
    user_input = request.args.get("video")
    # Vulnerable to shell injection
    os.system(f"ffmpeg -i {user_input} output.mp4")
    return "Processing started!"

if __name__ == "__main__":
    app.run()
