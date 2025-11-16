# worker.py
import threading, time, base64, io, os
from queue import Queue
from PIL import Image
import cv2
import numpy as np

# import your simulation engine and detectors
# sim_engine should expose an object that can run headless and provide a .step() or .get_state()
# For now, we adapt to a simple pattern:
# - Start one detector thread per video that pushes events into an event queue
# - Sim_engine runs headless and can accept events and returns a dict state and a PIL.Image for preview.

from detectors import VideoAudioDetectorThread
from sim_engine import HeadlessSim

class SimulationWorker(threading.Thread):
    def __init__(self, socketio, videos):
        super().__init__(daemon=True)
        self.socketio = socketio
        self.videos = videos  # dict with keys north/east/south/west -> file paths
        self.running = False
        self.pause = False
        self.event_q = Queue()
        self.det_threads = []
        self.sim = None

    def start(self):
        self.running = True
        super().start()

    def is_running(self):
        return self.running

    def stop(self):
        self.running = False
        # stop detectors
        for t in self.det_threads:
            t.stop()
        if self.sim:
            self.sim.stop()

    def toggle_pause(self):
        self.pause = not self.pause
        # forward to sim (which can pause the video readers)
        if self.sim:
            self.sim.set_paused(self.pause)

    def run(self):
        # start detector threads (send their events to self.event_q)
        for side in ("north","east","south","west"):
            path = self.videos.get(side)
            if not path: continue
            # detectors' approach names are N/E/S/W by convention; map them
            ap = side[0].upper()
            t = VideoAudioDetectorThread(path, ap, self.event_q)
            t.start()
            self.det_threads.append(t)

        # start headless sim (you must implement this to accept event queue)
        self.sim = HeadlessSim(self.event_q, videos=self.videos)
        self.sim.start()

        # main emit loop: every 0.5s, get state + preview image and emit
        try:
            while self.running:
                if self.pause:
                    time.sleep(0.2)
                    continue
                state, preview_img = self.sim.get_state_and_frame()  # state = dict, preview_img = np.array BGR
                # convert preview_img to JPEG base64
                _, jpg = cv2.imencode('.jpg', preview_img, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
                b64 = base64.b64encode(jpg.tobytes()).decode('ascii')
                payload = {
                    "state": state,
                    "frame": "data:image/jpeg;base64," + b64
                }
                # emit to all connected clients
                self.socketio.emit("state_update", payload)
                time.sleep(0.4)
        finally:
            # cleanup
            for t in self.det_threads:
                t.stop()
            if self.sim:
                self.sim.stop()
            self.running = False
