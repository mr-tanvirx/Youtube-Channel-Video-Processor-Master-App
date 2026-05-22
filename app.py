import os
import threading
import time
import socket
import webbrowser
import tkinter as tk
from tkinter import filedialog
from flask import Flask, render_template, request, jsonify
from tasks import process_jobs

app = Flask(__name__)

state = {
    "status": "Idle",
    "progress": 0,
    "eta": "--:--",
    "logs": ["System initialized and ready."]
}
cancel_event = threading.Event()
start_time = None

def update_status(status=None, progress=None, log=None):
    global start_time
    if status is not None: 
        state["status"] = status
        if status == "Processing":
            start_time = time.time()
            state["eta"] = "Calculating..."
        elif status in ["Completed", "Error", "Cancelled"]:
            state["eta"] = "--:--"
            
    if progress is not None: 
        state["progress"] = progress
        if start_time and progress > 0 and state["status"] == "Processing":
            elapsed = time.time() - start_time
            total_est = elapsed / (progress / 100.0)
            eta_seconds = max(0, total_est - elapsed)
            m, s = divmod(int(eta_seconds), 60)
            h, m = divmod(m, 60)
            state["eta"] = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

    if log is not None:
        state["logs"].append(log)
        if len(state["logs"]) > 100:
            state["logs"] = state["logs"][-100:]

def background_worker(config):
    try:
        process_jobs(config, update_status, cancel_event)
        if not cancel_event.is_set():
            update_status(status="Completed", progress=100, log="All requested tasks finished successfully.")
        else:
            update_status(status="Cancelled", log="Job was cancelled by the user.")
    except Exception as e:
        update_status(status="Error", log=f"Fatal Error: {str(e)}")
    finally:
        cancel_event.clear()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/browse")
def browse():
    """Opens a native Windows file/folder dialog and returns the selected path."""
    browse_type = request.args.get('type')
    
    root = tk.Tk()
    root.attributes('-topmost', True)
    root.withdraw()
    
    path = ""
    try:
        if browse_type == 'file':
            path = filedialog.askopenfilename(title="Select Video File", filetypes=[("Video files", "*.mp4 *.mkv *.avi *.mov")])
        elif browse_type == 'folder':
            path = filedialog.askdirectory(title="Select Folder")
    finally:
        root.destroy()
        
    return jsonify({"path": path})

@app.route("/start", methods=["POST"])
def start_processing():
    if state["status"] == "Processing":
        return jsonify({"error": "A job is already running."}), 400

    config = request.json
    cancel_event.clear()
    state["logs"] = ["Starting new job..."]
    state["progress"] = 0
    update_status(status="Processing")
    
    thread = threading.Thread(target=background_worker, args=(config,))
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": "Job started successfully."})

@app.route("/cancel", methods=["POST"])
def cancel_processing():
    if state["status"] == "Processing":
        cancel_event.set()
        return jsonify({"message": "Cancellation requested. Terminating processes..."})
    return jsonify({"error": "No active job to cancel."}), 400

@app.route("/status")
def get_status():
    return jsonify(state)

def get_free_port(start_port=5000):
    port = start_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
        port += 1

if __name__ == "__main__":
    from waitress import serve
    import logging
    logging.getLogger('waitress.queue').setLevel(logging.ERROR)
    
    port = get_free_port(5000)
    print(f"[INFO] Server starting on http://127.0.0.1:{port}")
    
    threading.Timer(1.25, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    
    serve(app, host="127.0.0.1", port=port)