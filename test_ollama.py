import json
import os
import sys

sys.path.insert(0, os.path.abspath('src'))

from ai_quality_platform.providers.base import create_provider
from ai_quality_platform.review import review_diff

def main():
    print("Testing Ollama provider with model: qwen3:4b-instruct...")
    try:
        provider = create_provider("ollama", "qwen3:4b-instruct", timeout_seconds=120)
    except Exception as e:
        print(f"Failed to create provider: {e}")
        return

    diff_text = """
diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -10,3 +10,4 @@
 def process_video(filename):
-    os.system(f"ffmpeg -i {filename} output.mp4")
+    user_input = request.args.get("video")
+    os.system(f"ffmpeg -i {user_input} output.mp4")
"""

    print("Sending diff to Ollama...")
    result = review_diff(diff_text, provider)
    
    print("\n" + "="*40)
    print("--- Review Result ---")
    print(f"Verdict: {result.verdict}")
    print(f"Summary: {result.summary}")
    print(f"Tokens Used: {result.usage_tokens}")
    print("Findings:")
    for f in result.findings:
        print(f"  - [{f.severity}] {f.title} ({f.category})")
        print(f"    {f.description}")
        print(f"    Recommendation: {f.recommendation}")
        print(f"    Blocking: {f.blocking}")
        print()
    print("="*40)

if __name__ == "__main__":
    main()
