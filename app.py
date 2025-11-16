# app.py
import os
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
import threading
import shutil
from worker import SimulationWorker

UPLOAD_FOLDER = "uploads"
ALLOWED_EXT = {"mp4","avi","mov","mkv"}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SECRET_KEY"] = "change_this_secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

worker = None
worker_lock = threading.Lock()

def allowed_file(filename):
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_EXT

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    """
    Expects 4 files with keys: north,east,south,west
    """
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    # clear old
    for f in os.listdir(UPLOAD_FOLDER):
        path = os.path.join(UPLOAD_FOLDER, f)
        os.remove(path)
    saved = {}
    for key in ("north","east","south","west"):
        file = request.files.get(key)
        if file and allowed_file(file.filename):
            fname = secure_filename(file.filename)
            dest = os.path.join(UPLOAD_FOLDER, f"{key}_{fname}")
            file.save(dest)
            saved[key] = dest
    if len(saved) < 1:
        return jsonify({"ok":False,"message":"No files uploaded"}), 400
    return jsonify({"ok":True,"files":saved})

@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@socketio.on("start_sim")
def on_start(data):
    global worker 
    with worker_lock:
        if worker and worker.is_running():
            emit("status", {"ok":False, "msg":"Worker already running"})
            return
        videos = data.get("videos", {})
        # start worker thread
        worker = SimulationWorker(socketio, videos)
        worker.start()
        emit("status", {"ok":True, "msg":"Simulation started"})

@socketio.on("stop_sim")
def on_stop():
    global worker
    with worker_lock:
        if worker:
            worker.stop()
            worker = None
            emit("status", {"ok":True, "msg":"Stopped"})
        else:
            emit("status", {"ok":False, "msg":"Not running"})

@socketio.on("pause_videos")
def on_pause():
    global worker
    if worker:
        worker.toggle_pause()
        emit("status", {"ok":True})


if __name__ == "__main__":
    print("🚀 Starting Flask SocketIO server (Werkzeug, no eventlet)...")
    socketio.run(app, host="127.0.0.1", port=5000, debug=False, use_reloader=False)

