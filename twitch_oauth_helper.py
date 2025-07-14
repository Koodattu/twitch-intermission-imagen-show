import os
from dotenv import load_dotenv
import threading
import webbrowser
from flask import Flask, request
import requests

# === CONFIG ===
load_dotenv()
CLIENT_ID = os.getenv('TWITCH_APP_KEY')
CLIENT_SECRET = os.getenv('TWITCH_APP_SECRET')
REDIRECT_URI = 'http://localhost:8888/callback'
SCOPES = 'chat:read chat:edit channel:read:redemptions'

# === FLASK SERVER ===
app = Flask(__name__)
tokens = {}

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return "Error: No code in request.", 400

    # Exchange code for tokens
    resp = requests.post(
        'https://id.twitch.tv/oauth2/token',
        params={
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': REDIRECT_URI
        }
    )
    data = resp.json()
    access_token = data.get('access_token')
    refresh_token = data.get('refresh_token')

    if not access_token:
        return f"Failed to get tokens: {data}", 400

    tokens['access_token'] = access_token
    tokens['refresh_token'] = refresh_token

    # Print to console
    print('\n\n==== TOKENS RECEIVED! ====')
    print(f"ACCESS_TOKEN: {access_token}")
    print(f"REFRESH_TOKEN: {refresh_token}")
    print('\nCopy these tokens to your .env file.\n')

    # Schedule shutdown after response is sent
    threading.Timer(1.0, shutdown_server).start()
    return "You can close this browser tab and stop the script. Tokens printed in the console!"

def shutdown_server():
    print("Shutting down server...")
    os._exit(0)

def run_flask():
    app.run(port=8888)

def main():
    # 1. Start Flask server in background (non-daemon)
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # 2. Build auth URL and open browser
    auth_url = (
        f"https://id.twitch.tv/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={SCOPES.replace(' ', '%20')}"
    )
    print(f"\nOpen this link in your browser if it does not open automatically:\n{auth_url}\n")
    webbrowser.open(auth_url)

    # 3. Wait for tokens
    while not tokens:
        pass  # Wait for callback

    # 4. Wait for Flask thread to finish cleanly
    flask_thread.join()


if __name__ == '__main__':
    main()
