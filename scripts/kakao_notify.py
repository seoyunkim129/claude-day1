"""Send a KakaoTalk 'memo to me' message. Requires scripts/kakao_auth.py to have run once.

Usage:
    python scripts/kakao_notify.py "message text"
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ENV_PATH = ".env"
SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"


def load_env():
    env = dict(os.environ)
    if os.path.exists(ENV_PATH):
        for line in open(ENV_PATH, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip())
    return env


def save_access_token(access_token):
    lines = open(ENV_PATH, encoding="utf-8").read().splitlines()
    out = [f"KAKAO_ACCESS_TOKEN={access_token}" if l.startswith("KAKAO_ACCESS_TOKEN=") else l for l in lines]
    open(ENV_PATH, "w", encoding="utf-8").write("\n".join(out) + "\n")


def refresh_access_token(env):
    data = {
        "grant_type": "refresh_token",
        "client_id": env["KAKAO_REST_API_KEY"],
        "refresh_token": env["KAKAO_REFRESH_TOKEN"],
    }
    if env.get("KAKAO_CLIENT_SECRET"):
        data["client_secret"] = env["KAKAO_CLIENT_SECRET"]
    req = urllib.request.Request(
        TOKEN_URL,
        data=urllib.parse.urlencode(data).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
    )
    with urllib.request.urlopen(req) as resp:
        tokens = json.load(resp)
    save_access_token(tokens["access_token"])
    return tokens["access_token"]


def send(access_token, text):
    template = {"object_type": "text", "text": text}
    req = urllib.request.Request(
        SEND_URL,
        data=urllib.parse.urlencode({"template_object": json.dumps(template)}).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    env = load_env()
    access_token = env.get("KAKAO_ACCESS_TOKEN")
    if not access_token:
        print("Run scripts/kakao_auth.py first")
        sys.exit(1)
    text = sys.argv[1]
    try:
        result = send(access_token, text)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            access_token = refresh_access_token(env)
            result = send(access_token, text)
        else:
            raise
    print(result)


if __name__ == "__main__":
    main()
