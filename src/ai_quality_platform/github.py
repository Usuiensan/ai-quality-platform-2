import json
import os
import subprocess
import urllib.error
import urllib.request

def get_pr_number() -> int | None:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        return None
    try:
        with open(event_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "pull_request" in data:
                return data["pull_request"]["number"]
    except Exception:
        pass
    return None

def post_pr_comment(body: str) -> bool:
    repo = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    if not repo or not token:
        print("Missing GITHUB_REPOSITORY or GITHUB_TOKEN environment variables.")
        return False
        
    pr_number = get_pr_number()
    if not pr_number:
        print("Could not determine PR number. Are you running in a pull_request event?")
        return False

    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }
    payload = {"body": body}
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 201:
                print("Successfully posted PR comment.")
                return True
            print(f"Failed to post PR comment. HTTP Status: {response.status}")
            return False
    except urllib.error.URLError as e:
        print(f"Failed to post PR comment: {e}")
        if hasattr(e, 'read'):
            print(e.read().decode("utf-8"))
        return False

def git_commit_and_push(message: str) -> bool:
    try:
        # Check if there are changes
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, encoding="utf-8")
        if not status.stdout.strip():
            print("No changes to commit.")
            return True
            
        # Configure git if not configured
        user_name = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True, encoding="utf-8").stdout.strip()
        if not user_name:
            subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
            subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)
        
        # Add, commit, push
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", message], check=True)
        
        # When running in GH Actions, we need to push to the PR branch
        # GITHUB_HEAD_REF is the branch name of the PR
        head_ref = os.environ.get("GITHUB_HEAD_REF")
        if head_ref:
            subprocess.run(["git", "push", "origin", f"HEAD:{head_ref}"], check=True)
        else:
            subprocess.run(["git", "push"], check=True)
        print("Successfully committed and pushed changes.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to commit and push: {e}")
        return False
