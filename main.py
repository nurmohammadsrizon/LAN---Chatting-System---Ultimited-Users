from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from auth import create_token, decode_token, hash_password, verify_password
from database.storage import get_all, replace_all

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Srizon Message", version="2.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

DB_LOCK = asyncio.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {"id": user["id"], "username": user["username"], "display_name": user["display_name"], "created_at": user["created_at"]}


def find_user_by_id(user_id: str) -> dict[str, Any] | None:
    return next((u for u in get_all("users") if u["id"] == user_id), None)


def find_user_by_username(username: str) -> dict[str, Any] | None:
    lower = username.casefold()
    return next((u for u in get_all("users") if u["username"].casefold() == lower), None)


def get_group(group_id: str) -> dict[str, Any] | None:
    return next((g for g in get_all("groups") if g["id"] == group_id), None)

PUBLIC_GROUP_ID = "public_lounge"

def ensure_public_group() -> dict[str, Any]:
    groups = get_all("groups")
    users = get_all("users")
    group = next((g for g in groups if g.get("id") == PUBLIC_GROUP_ID), None)
    member_ids = [u["id"] for u in users]
    if group is None:
        group = {"id": PUBLIC_GROUP_ID, "name": "Public Lounge", "member_ids": member_ids, "public": True, "created_at": now_iso()}
        replace_all("groups", [group])
    else:
        changed = False
        for uid in member_ids:
            if uid not in group.setdefault("member_ids", []):
                group["member_ids"].append(uid); changed = True
        group["member_ids"] = sorted(set(group["member_ids"]))
        group["public"] = True
        if changed:
            replace_all("groups", groups)
    return group


def get_direct_conversation_id(user_a: str, user_b: str) -> str:
    pair = sorted([user_a, user_b])
    return f"dm_{pair[0]}_{pair[1]}"


def user_has_group(user_id: str, group: dict[str, Any]) -> bool:
    return user_id in group.get("member_ids", [])


class SignupBody(BaseModel):
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class LoginBody(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    password: str = Field(min_length=1, max_length=128)


class MessageBody(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    chat_type: str = Field(pattern=r"^(group|personal)$")
    target_id: str
    reply_to: str | None = None


class DeleteBody(BaseModel):
    message_id: str


async def require_user_from_token(token: str) -> dict[str, Any]:
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = find_user_by_id(payload.get("sub", ""))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def bearer_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return await require_user_from_token(authorization[7:])


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.setdefault(user_id, set()).add(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        group = self.connections.get(user_id)
        if not group:
            return
        group.discard(websocket)
        if not group:
            self.connections.pop(user_id, None)

    async def send_user(self, user_id: str, payload: dict[str, Any]) -> None:
        sockets = list(self.connections.get(user_id, set()))
        dead = []
        for socket in sockets:
            try:
                await socket.send_json(payload)
            except Exception:
                dead.append(socket)
        for socket in dead:
            self.disconnect(user_id, socket)

    async def send_users(self, user_ids: set[str], payload: dict[str, Any]) -> None:
        await asyncio.gather(*(self.send_user(uid, payload) for uid in user_ids))


manager = ConnectionManager()



@app.on_event("startup")
async def startup_initialize() -> None:
    async with DB_LOCK:
        users_data = get_all("users")
        groups_data = get_all("groups")
        public = next((g for g in groups_data if g.get("id") == PUBLIC_GROUP_ID), None)
        member_ids = sorted(u["id"] for u in users_data)
        if public is None:
            groups_data = [{"id": PUBLIC_GROUP_ID, "name": "Public Lounge", "member_ids": member_ids, "public": True, "created_at": now_iso()}]
            replace_all("groups", groups_data)
        else:
            public["name"] = "Public Lounge"
            public["public"] = True
            public["member_ids"] = member_ids
            replace_all("groups", groups_data)

@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/auth/signup")
async def signup(body: SignupBody):
    async with DB_LOCK:
        if find_user_by_username(body.username):
            raise HTTPException(status_code=409, detail="Username already exists")
        user = {
            "id": str(uuid4()),
            "username": body.username,
            "display_name": body.display_name.strip() or body.username,
            "password_hash": hash_password(body.password),
            "created_at": now_iso(),
        }
        users = get_all("users")
        users.append(user)
        replace_all("users", users)
        groups = get_all("groups")
        public = next((g for g in groups if g.get("id") == PUBLIC_GROUP_ID), None)
        if public is None:
            groups = [{"id": PUBLIC_GROUP_ID, "name": "Public Lounge", "member_ids": [u["id"] for u in users], "public": True, "created_at": now_iso()}]
        else:
            public["member_ids"] = sorted(set(public.get("member_ids", [])) | {user["id"]})
            public["public"] = True
        replace_all("groups", groups)
    return {"token": create_token(user["id"]), "user": public_user(user)}


@app.post("/api/auth/login")
async def login(body: LoginBody):
    user = find_user_by_username(body.username)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {"token": create_token(user["id"]), "user": public_user(user)}


@app.get("/api/me")
async def me(user: dict[str, Any] = Depends(bearer_user)):
    return public_user(user)


@app.get("/api/users")
async def users(user: dict[str, Any] = Depends(bearer_user)):
    all_users = [public_user(u) for u in get_all("users")]
    all_users.sort(key=lambda x: x["display_name"].casefold())
    return {"users": all_users, "current_user_id": user["id"]}


@app.post("/api/groups")
async def create_group_disabled(user: dict[str, Any] = Depends(bearer_user)):
    raise HTTPException(status_code=403, detail="Users cannot create groups")


@app.get("/api/chats")
async def chats(user: dict[str, Any] = Depends(bearer_user)):
    all_users = [public_user(u) for u in get_all("users") if u["id"] != user["id"]]
    groups = [g for g in get_all("groups") if g.get("id") == PUBLIC_GROUP_ID]
    return {"personal": all_users, "groups": groups}


@app.get("/api/history/{chat_type}/{target_id}")
async def history(chat_type: str, target_id: str, user: dict[str, Any] = Depends(bearer_user)):
    if chat_type == "personal":
        other = find_user_by_id(target_id)
        if not other or other["id"] == user["id"]:
            raise HTTPException(404, "User not found")
        conversation_id = get_direct_conversation_id(user["id"], other["id"])
    elif chat_type == "group":
        group = get_group(target_id)
        if not group or target_id != PUBLIC_GROUP_ID:
            raise HTTPException(404, "Public group not found")
        conversation_id = PUBLIC_GROUP_ID
    else:
        raise HTTPException(400, "Invalid chat type")

    messages = [m for m in get_all("messages") if m["conversation_id"] == conversation_id and not m.get("deleted")]
    return {"messages": messages}


@app.post("/api/messages")
async def send_message(body: MessageBody, user: dict[str, Any] = Depends(bearer_user)):
    if body.chat_type == "personal":
        other = find_user_by_id(body.target_id)
        if not other or other["id"] == user["id"]:
            raise HTTPException(404, "User not found")
        conversation_id = get_direct_conversation_id(user["id"], other["id"])
        recipients = {user["id"], other["id"]}
    else:
        group = get_group(body.target_id)
        if not group or body.target_id != PUBLIC_GROUP_ID:
            raise HTTPException(404, "Public group not found")
        conversation_id = PUBLIC_GROUP_ID
        recipients = {u["id"] for u in get_all("users")}

    reply_preview = None
    if body.reply_to:
        found = next((m for m in get_all("messages") if m["id"] == body.reply_to and m["conversation_id"] == conversation_id and not m.get("deleted")), None)
        if not found:
            raise HTTPException(400, "Reply target not found")
        reply_preview = {"id": found["id"], "username": found["username"], "text": found["text"][:180]}

    message = {
        "id": str(uuid4()),
        "conversation_id": conversation_id,
        "chat_type": body.chat_type,
        "sender_id": user["id"],
        "username": user["display_name"],
        "text": body.text.strip(),
        "timestamp": now_iso(),
        "reply_to": reply_preview,
        "deleted": False,
    }
    async with DB_LOCK:
        messages = get_all("messages")
        messages.append(message)
        replace_all("messages", messages)

    await manager.send_users(recipients, {"type": "message", "message": message})
    return message


@app.delete("/api/messages/{message_id}")
async def delete_message(message_id: str, user: dict[str, Any] = Depends(bearer_user)):
    async with DB_LOCK:
        messages = get_all("messages")
        target = next((m for m in messages if m["id"] == message_id), None)
        if not target:
            raise HTTPException(404, "Message not found")
        if target["sender_id"] != user["id"]:
            raise HTTPException(403, "You can delete only your own messages")
        target["deleted"] = True
        target["text"] = "This message was deleted."
        replace_all("messages", messages)

    if target["chat_type"] == "personal":
        recipients = {user["id"], target["conversation_id"].split("_")[1], target["conversation_id"].split("_")[2]}
        recipients.discard("")
    else:
        recipients = {u["id"] for u in get_all("users")} if target["conversation_id"] == PUBLIC_GROUP_ID else {user["id"]}
    await manager.send_users(recipients, {"type": "message_deleted", "message_id": message_id})
    return {"ok": True}


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    payload = decode_token(token)
    if not payload:
        await websocket.close(code=1008)
        return
    user = find_user_by_id(payload.get("sub", ""))
    if not user:
        await websocket.close(code=1008)
        return

    user_id = user["id"]
    await manager.connect(user_id, websocket)
    await manager.send_user(user_id, {"type": "presence", "online": True, "user_id": user_id})
    try:
        while True:
            # Client can keep connection alive or send lightweight pings.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
        if user_id not in manager.connections:
            await manager.send_users(set(u["id"] for u in get_all("users") if u["id"] != user_id), {"type": "presence", "online": False, "user_id": user_id})
