# Crown & Court — Web Multiplayer

Play Crown & Court online with 3 friends in a shared lobby.

## Play Locally (dev)

### Terminal 1 — server
```bash
cd crown-and-court
pip install -e .
pip install -r web/requirements.txt
python -m uvicorn web.server.main:app --host 0.0.0.0 --port 8000 --reload
```

### Terminal 2 — client (hot reload)
```bash
cd web/client
npm install
npm run dev
```

Open http://localhost:5173

---

## Play With Friends Remotely

Deploy **one service** that serves both the game UI and WebSocket server. Friends only need the public URL.

### Option A — Railway (recommended, ~5 min)

1. Push this repo to GitHub.
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**.
3. Select your repo. Railway reads [`railway.toml`](../railway.toml) and builds `web/Dockerfile`.
4. After deploy, open **Settings → Networking → Generate Domain**.
5. Share that URL with friends (e.g. `https://crown-court-production.up.railway.app`).

**Invite flow:** Host creates a lobby → **Copy Invite Link** → friends open the link and enter their name.

### Option B — Render

1. Push to GitHub.
2. Go to [render.com](https://render.com) → **New Blueprint** → connect repo.
3. Render reads [`render.yaml`](../render.yaml) and deploys the Docker image.
4. Share the generated `.onrender.com` URL.

### Option C — Docker on any VPS

```bash
cd crown-and-court
docker build -f web/Dockerfile -t crown-court .
docker run -p 8000:8000 crown-court
```

Point a domain at the server (or use the VPS IP). For HTTPS, put Caddy/nginx in front.

### Option D — Quick test with ngrok (no deploy)

```bash
# Terminal 1: start production-like server locally
cd crown-and-court
docker build -f web/Dockerfile -t crown-court .
docker run -p 8000:8000 crown-court

# Terminal 2: expose to internet
ngrok http 8000
```

Share the `https://….ngrok-free.app` URL. Free ngrok URLs change each session.

---

## Production architecture

```
https://your-domain.com/          → React game UI (static)
wss://your-domain.com/ws          → WebSocket game server
https://your-domain.com/health      → Health check
```

One URL, no separate client/server config needed.

---

## Game Structure

- **4 players** per game
- **4 matches** — each player starts as King once
- **4 rounds** per match
- **10 points** to win (or highest score after 4 matches)

## Reconnect

Session tokens are stored in the browser. Refreshing the page reconnects you to the same seat.

## Tests

```bash
pytest tests/test_web_multiplayer.py -v
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Connection failed" | Server not running or wrong URL. Check `/health` returns `{"status":"ok"}`. |
| Friends can't join | Use the **public** deploy URL, not `localhost`. |
| Room disappears | Server restarted — rooms are in-memory. Start a new lobby. |
| WebSocket errors on Render free tier | Free tier sleeps after inactivity; first visit may take ~30s to wake. |
