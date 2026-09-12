# Srizon Message

A lightweight realtime chat app built with FastAPI + WebSocket + JSON file storage.

## Features

- Signup / Login with PBKDF2-SHA256 password hashing
- Persistent JSON storage; no PostgreSQL/MySQL
- Authentication with signed tokens
- One fixed public group: **Public Lounge**
- Users cannot create groups
- Personal DM with any other registered user
- Persistent message history after server restart
- Reply to a specific message
- Delete your own messages
- Realtime WebSocket delivery
- Automatic WebSocket reconnect
- Responsive phone/tablet/desktop UI
- White glassmorphism + fluid animated UI
- Mobile keyboard-safe composer with iPhone-style floating send button

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000`.

For another device on the same LAN, open `http://YOUR-PC-IP:8000`.

## Data

The `database/` directory stores:

- `users.json`
- `groups.json`
- `messages.json`
- `.secret_key` (created by the authentication module)

The server automatically maintains the fixed `public_lounge` room and syncs all registered users into it.
