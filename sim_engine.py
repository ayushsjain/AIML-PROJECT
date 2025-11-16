import time
import numpy as np
import cv2
from preemption_fsm import PreemptionFSM, State


class HeadlessSim:
    def __init__(self, event_queue, videos=None):
        self.q = event_queue
        self.videos = videos or {}

        self.running = False
        self.pause = False

        self.detected_path = None  # N/E/S/W

        # queues for normal + emergency vehicles per direction
        self.queues = {k: [] for k in "NESW"}

        # initial signals
        self.signals = {"N": "R", "E": "R", "S": "R", "W": "R"}

        # timer for spawning cars
        self.spawn_timer = 0.0

        # FSM (3 sec latency, 12 sec max hold, 1.5 sec grace)
        self.fsm = PreemptionFSM(latency_ms=3000, max_hold_ms=12000, grace_ms=1500)

    # ------------------------------------------------------------------
    # CONTROL HANDLERS
    # ------------------------------------------------------------------
    def start(self):
        """Start simulation loop in background thread."""
        self.running = True
        import threading
        t = threading.Thread(target=self._run)
        t.daemon = True
        t.start()

    def stop(self):
        self.running = False

    def pause_sim(self):
        self.pause = True

    def resume_sim(self):
        self.pause = False

    # ------------------------------------------------------------------
    # MAIN SIMULATION LOOP
    # ------------------------------------------------------------------
    def run(self):
    print("[Worker] Started simulation thread")

    while self.running:
        # get state + frame from sim
        state, preview_img = self.sim.get_state_and_frame()

        # emit to frontend
        try:
            self.socketio.emit("sim_update", {
                "state": state,
                "img": self._encode(preview_img)
            })
        except Exception as e:
            print("[Worker] Emit error:", e)

        time.sleep(0.05)  # 20 FPS

    # ------------------------------------------------------------------
    # UI FRAME + STATE GENERATOR  (THIS IS THE MISSING FUNCTION)
    # ------------------------------------------------------------------
    def get_state_and_frame(self):
        """
        Returns:
            state_dict: simulation info for UI
            frame: 800x600 BGR image for canvas
        """

        # ------------- 1. BUILD STATE DICTIONARY -----------------
        state = {
            "signals": self.signals,
            "detected_path": self.detected_path,
            "vehicles": {
                d: [
                    {"pos": v["pos"], "is_amb": v["is_amb"]}
                    for v in self.queues[d]
                ]
                for d in "NESW"
            }
        }

        # ------------- 2. GENERATE PREVIEW FRAME -----------------
        frame = np.zeros((600, 800, 3), dtype=np.uint8)

        # draw roads
        cv2.rectangle(frame, (300, 0), (500, 600), (80, 80, 80), -1)
        cv2.rectangle(frame, (0, 250), (800, 350), (80, 80, 80), -1)

        # draw signals
        sig_pos = {
            "N": (390, 20),
            "S": (390, 520),
            "E": (620, 290),
            "W": (160, 290)
        }

        for d, c in self.signals.items():
            color = (0, 255, 0) if c == "G" else (0, 0, 255)
            cv2.circle(frame, sig_pos[d], 18, color, -1)

        # draw vehicles
        colors = {
            "N": (255, 0, 255),
            "E": (255, 255, 0),
            "S": (255, 255, 255),
            "W": (0, 255, 255)
        }

        for d in "NESW":
            for v in self.queues[d]:
                x, y = self._vehicle_to_xy(d, v["pos"])
                col = (0, 255, 255) if v["is_amb"] else colors[d]
                cv2.rectangle(frame, (x, y), (x + 20, y + 20), col, -1)

        return state, frame

    # ------------------------------------------------------------------
    # MAP LOGICAL POSITION TO SCREEN COORDINATES
    # ------------------------------------------------------------------
    def _vehicle_to_xy(self, direction, pos):
        pos = int(pos)

        if direction == "N":
            return (380, pos)
        if direction == "S":
            return (420, pos)
        if direction == "E":
            return (pos, 265)
        if direction == "W":
            return (pos, 305)

        return (0, 0)
