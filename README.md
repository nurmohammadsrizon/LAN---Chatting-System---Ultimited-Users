# LAN Real-time Chat (FastAPI + WebSockets)

A real-time chat app that works between any devices on the same Wi-Fi/LAN.
Tested end-to-end (two simulated clients joining, chatting, and leaving) —
see "How this was tested" below.

## Setup

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- `--host 0.0.0.0` is required so other devices on your network can connect.
- Drop `--reload` for anything other than active development.

## Connect

Find your machine's local IP:

| OS      | Command                              |
|---------|---------------------------------------|
| Linux   | `ip addr` or `hostname -I`            |
| macOS   | `ipconfig getifaddr en0`              |
| Windows | `ipconfig`                            |

Then, on any device on the same Wi-Fi:

- This computer: `http://localhost:8000`
- Other devices: `http://<your-local-ip>:8000` (e.g. `http://192.168.1.42:8000`)

Enter a name, hit "Join Chat", and start messaging. Open it on a second
device to see messages appear instantly on both.

## Troubleshooting

| Problem | Fix |
|---|---|
| Other device can't load the page | Confirm same Wi-Fi, confirm `--host 0.0.0.0` was used, check firewall allows port 8000 |
| Works on localhost, not on phone | You forgot `--host 0.0.0.0` |
| "Connection refused" | Server isn't running, or wrong IP/port |
| Phone still can't connect | Router may have AP/Client Isolation enabled — turn it off |

Windows Firewall quick fix:
```powershell
New-NetFirewallRule -DisplayName "FastAPI Chat" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

## How this was tested

Before delivering, I ran the server and simulated two WebSocket clients
(Alice and Bob) connecting, messaging, and disconnecting. Confirmed:
- Both clients get a "joined the chat" system message.
- A message sent by Alice is broadcast to both Alice and Bob instantly.
- A message sent by Bob is broadcast to both instantly.
- Disconnecting triggers a "left the chat" broadcast to remaining clients.

## Next features (pick one and I'll build it)

1. **Message history** — keep last 50 messages, send on connect (easy)
2. **Typing indicator** (medium)
3. **Multiple chat rooms** — `/ws/{room_id}` (medium)
4. **File/image sharing** (medium)
5. **Online user list** (easy)
6. **Dark/light theme toggle** (easy)
7. **Persistent storage** — SQLite/PostgreSQL (medium)
8. **Authentication** — JWT or password (harder)
9. **Deploy outside LAN** — ngrok / Cloudflare Tunnel / VPS (medium)
