"""One-time Kakao OAuth login for the 'send to me' message API.

Usage:
    python scripts/kakao_auth.py
"""
import json
import os
import secrets
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

ENV_PATH = ".env"


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


def save_tokens(access_token, refresh_token):
    lines = open(ENV_PATH, encoding="utf-8").read().splitlines() if os.path.exists(ENV_PATH) else []
    seen = {"KAKAO_ACCESS_TOKEN": False, "KAKAO_REFRESH_TOKEN": False}
    out = []
    for line in lines:
        if line.startswith("KAKAO_ACCESS_TOKEN="):
            out.append(f"KAKAO_ACCESS_TOKEN={access_token}")
            seen["KAKAO_ACCESS_TOKEN"] = True
        elif line.startswith("KAKAO_REFRESH_TOKEN="):
            out.append(f"KAKAO_REFRESH_TOKEN={refresh_token}")
            seen["KAKAO_REFRESH_TOKEN"] = True
        else:
            out.append(line)
    if not seen["KAKAO_ACCESS_TOKEN"]:
        out.append(f"KAKAO_ACCESS_TOKEN={access_token}")
    if not seen["KAKAO_REFRESH_TOKEN"]:
        out.append(f"KAKAO_REFRESH_TOKEN={refresh_token}")
    open(ENV_PATH, "w", encoding="utf-8").write("\n".join(out) + "\n")


def main():
    env = load_env()
    client_id = env.get("KAKAO_REST_API_KEY")
    client_secret = env.get("KAKAO_CLIENT_SECRET", "")
    redirect_uri = env.get("KAKAO_REDIRECT_URI", "http://localhost:8766/callback")
    if not client_id:
        print("Set KAKAO_REST_API_KEY in .env first")
        return

    state = secrets.token_urlsafe(16)
    port = int(urllib.parse.urlsplit(redirect_uri).port or 8766)
    authorize_url = "https://kauth.kakao.com/oauth/authorize?" + urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "talk_message",
            "state": state,
        }
    )

    result = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            qs = urllib.parse.urlsplit(self.path).query
            params = urllib.parse.parse_qs(qs)
            result["code"] = params.get("code", [None])[0]
            result["state"] = params.get("state", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("로그인 완료. 이 창은 닫아도 됩니다.".encode("utf-8"))

        def log_message(self, *args):
            pass

    print("아래 URL을 직접 브라우저에서 열어 카카오 로그인 후 동의해주세요:\n")
    print(authorize_url)
    webbrowser.open(authorize_url)

    server = HTTPServer(("localhost", port), Handler)
    server.handle_request()

    if result.get("state") != state or not result.get("code"):
        print("로그인 실패 또는 state 불일치")
        return

    token_data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code": result["code"],
    }
    if client_secret:
        token_data["client_secret"] = client_secret

    req = urllib.request.Request(
        "https://kauth.kakao.com/oauth/token",
        data=urllib.parse.urlencode(token_data).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
    )
    with urllib.request.urlopen(req) as resp:
        tokens = json.load(resp)

    if "access_token" not in tokens:
        print("토큰 발급 실패:", tokens)
        return

    save_tokens(tokens["access_token"], tokens.get("refresh_token", ""))
    print("완료: .env에 KAKAO_ACCESS_TOKEN / KAKAO_REFRESH_TOKEN 저장됨")


if __name__ == "__main__":
    main()
