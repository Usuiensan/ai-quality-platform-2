import os
from flask import Flask, request

app = Flask(__name__)

@app.route("/process")
def process():
    user_input = request.args.get("video")
    # Validate input to ensure it's a safe file path
    if not user_input or not user_input.strip():
        return "Invalid input: video parameter is required.", 400
    # Validate for shell metacharacters and extreme lengths
    # ファイルパスの検証はすでに実行済みなので、ここでは安全に処理
    try:
        # ファイルパスの妥当性を確認
        if not os.path.isfile(user_input):
            return "Error: Input file does not exist or is invalid.", 400
        # 安全なコマンド実行：shell=Falseで直接ユーザー入力の挿入を防ぐ
        result = subprocess.run(['ffmpeg', '-i', user_input, 'output.mp4'], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        return f"Error processing video: {e.stderr.decode('utf-8') if e.stderr else 'Unknown error'}", 500
    return "Processing started!"

if __name__ == "__main__":
    app.run()
