from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import List
import json
from datetime import datetime

### Developeed by Nur Mohammad Srizon 
# It Will work in same wifi


app = FastAPI(title="LAN Real-time Chat")

# ========== Connection Manager ==========
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.usernames: dict[WebSocket, str] = {}  # websocket -> username

    async def connect(self, websocket: WebSocket, username: str = "Anonymous"):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.usernames[websocket] = username
        # Notify everyone that someone joined
        await self.broadcast({
            "type": "system",
            "message": f"{username} joined the chat",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })

    def disconnect(self, websocket: WebSocket):
        username = self.usernames.get(websocket, "Someone")
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.usernames:
            del self.usernames[websocket]
        return username

    async def broadcast(self, message: dict):
        """Send message to all connected clients as JSON"""
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)

        # Clean up dead connections
        for conn in dead_connections:
            self.disconnect(conn)

manager = ConnectionManager()

# ========== HTML Frontend ==========
html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CHAT WITH SRIZON TEAM</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        header {
            background: #16213e;
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #0f3460;
        }
        h1 { font-size: 1.3rem; }
        #status { font-size: 0.85rem; color: #4ade80; }
        #messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .message {
            max-width: 80%;
            padding: 10px 14px;
            border-radius: 12px;
            line-height: 1.4;
            word-wrap: break-word;
        }
        .message.own {
            background: #0f3460;
            align-self: flex-end;
            border-bottom-right-radius: 4px;
        }
        .message.other {
            background: #16213e;
            align-self: flex-start;
            border-bottom-left-radius: 4px;
        }
        .message.system {
            background: transparent;
            color: #94a3b8;
            font-size: 0.85rem;
            align-self: center;
            text-align: center;
        }
        .meta {
            font-size: 0.75rem;
            color: #94a3b8;
            margin-bottom: 3px;
        }
        #input-area {
            display: flex;
            padding: 15px;
            background: #16213e;
            border-top: 1px solid #0f3460;
            gap: 10px;
        }
        #messageInput {
            flex: 1;
            padding: 12px 16px;
            border: none;
            border-radius: 25px;
            background: #1a1a2e;
            color: white;
            font-size: 1rem;
            outline: none;
        }
        #sendBtn {
            padding: 12px 22px;
            border: none;
            border-radius: 25px;
            background: #e94560;
            color: white;
            font-weight: 600;
            cursor: pointer;
        }
        #sendBtn:hover { background: #ff6b81; }
        #username-modal {
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 100;
        }
        .modal-content {
            background: #16213e;
            padding: 30px;
            border-radius: 16px;
            width: 90%;
            max-width: 360px;
            text-align: center;
        }
        .modal-content input {
            width: 100%;
            padding: 12px;
            margin: 15px 0;
            border: none;
            border-radius: 8px;
            background: #1a1a2e;
            color: white;
            font-size: 1rem;
        }
        .modal-content button {
            width: 100%;
            padding: 12px;
            border: none;
            border-radius: 8px;
            background: #e94560;
            color: white;
            font-size: 1rem;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div id="username-modal">
        <div class="modal-content">
            <h2>Enter your name</h2>
            <input id="usernameInput" type="text" placeholder="Your name..." maxlength="20" autofocus>
            <button onclick="joinChat()">Join Chat</button>
        </div>
    </div>

    <header>
        <h1>CHAT WITH SRIZON</h1>
        <div id="status">Connecting...</div>
    </header>

    <div id="messages"></div>

    <div id="input-area">
        <input id="messageInput" type="text" placeholder="Type a message..." autocomplete="off" disabled>
        <button id="sendBtn" onclick="sendMessage()" disabled>Send</button>
    </div>

    <script>
        let ws = null;
        let username = "Anonymous";
        const messagesDiv = document.getElementById('messages');
        const input = document.getElementById('messageInput');
        const status = document.getElementById('status');
        const sendBtn = document.getElementById('sendBtn');

        function joinChat() {
            const nameInput = document.getElementById('usernameInput');
            username = nameInput.value.trim() || "Anonymous";
            document.getElementById('username-modal').style.display = 'none';
            connectWebSocket();
        }

        function connectWebSocket() {
            // Automatically use the same host (works for both localhost and LAN IP)
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws?username=${encodeURIComponent(username)}`);

            ws.onopen = () => {
                status.textContent = "Connected";
                status.style.color = "#4ade80";
                input.disabled = false;
                sendBtn.disabled = false;
                input.focus();
            };

            ws.onclose = () => {
                status.textContent = "Disconnected - Reconnecting...";
                status.style.color = "#f87171";
                input.disabled = true;
                sendBtn.disabled = true;
                setTimeout(connectWebSocket, 2000);  // auto reconnect
            };

            ws.onerror = () => {
                status.textContent = "Connection error";
                status.style.color = "#f87171";
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                addMessage(data);
            };
        }

        function addMessage(data) {
            const div = document.createElement('div');

            if (data.type === 'system') {
                div.className = 'message system';
                div.textContent = `[${data.timestamp}] ${data.message}`;
            } else {
                const isOwn = data.username === username;
                div.className = `message ${isOwn ? 'own' : 'other'}`;

                const meta = document.createElement('div');
                meta.className = 'meta';
                meta.textContent = `${data.username} \u2022 ${data.timestamp}`;

                const text = document.createElement('div');
                text.textContent = data.message;

                div.appendChild(meta);
                div.appendChild(text);
            }

            messagesDiv.appendChild(div);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function sendMessage() {
            const text = input.value.trim();
            if (text && ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    message: text
                }));
                input.value = '';
            }
        }

        // Enter key support
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });

        // Also allow Enter on username input
        document.getElementById('usernameInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') joinChat();
        });
    </script>
</body>
</html>
"""

@app.get("/")
async def get_chat_page():
    return HTMLResponse(html)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, username: str = "Anonymous"):
    await manager.connect(websocket, username)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                message_text = payload.get("message", "").strip()
            except Exception:
                message_text = data.strip()

            if message_text:
                await manager.broadcast({
                    "type": "chat",
                    "username": manager.usernames.get(websocket, "Anonymous"),
                    "message": message_text,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
    except WebSocketDisconnect:
        left_user = manager.disconnect(websocket)
        await manager.broadcast({
            "type": "system",
            "message": f"{left_user} left the chat",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
