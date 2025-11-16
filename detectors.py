# detectors.py
import threading
import time
import cv2
from queue import Queue
from ultralytics import YOLO
import numpy as np
import sounddevice as sd
from scipy.signal import find_peaks
from scipy.fft import rfft, rfftfreq

# ============ YOLO VIDEO DETECTOR ============= #
class VideoAudioDetectorThread(threading.Thread):
    def __init__(self, video_path, approach, event_q: Queue):
        super().__init__(daemon=True)
        self.video_path = video_path
        self.approach = approach  # "N","E","S","W"
        self.q = event_q
        self.running = True
        self.model = YOLO("yolov8n.pt")  # small fast model

    def stop(self):
        self.running = False

    def run(self):
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            print(f"[ERROR] Cannot open video {self.video_path}")
            return

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        interval = 1 / fps

        while self.running:
            ok, frame = cap.read()
            if not ok:
                break
            results = self.model.predict(source=frame, verbose=False)
            for r in results:
                for cls_name, conf in zip(r.names.values(), r.boxes.conf.tolist()):
                    if "ambulance" in cls_name.lower() and conf > 0.4:
                        self.q.put((self.approach, "video", float(conf)))
                        print(f"[DETECT] {self.approach} ambulance conf={conf:.2f}")
            time.sleep(interval)
        cap.release()


# ============ AUDIO SIREN DETECTOR (OPTIONAL) ============= #
class AudioSirenDetector(threading.Thread):
    def __init__(self, duration=1.0, samplerate=44100, approach="N", event_q=None):
        super().__init__(daemon=True)
        self.duration = duration
        self.samplerate = samplerate
        self.approach = approach
        self.event_q = event_q
        self.running = True

    def stop(self):
        self.running = False

    def run(self):
        print(f"[INFO] Audio siren detector started for {self.approach}")
        while self.running:
            audio = sd.rec(int(self.duration * self.samplerate),
                           samplerate=self.samplerate, channels=1, dtype='float32')
            sd.wait()
            freqs = np.abs(rfft(audio[:, 0]))
            peaks, _ = find_peaks(freqs, height=0.3)
            if len(peaks) > 0:
                dominant_freq = rfftfreq(len(audio[:, 0]), 1 / self.samplerate)[peaks[0]]
                if 600 < dominant_freq < 1600:  # siren frequency range
                    print(f"[AUDIO] Siren detected at {dominant_freq:.0f} Hz on {self.approach}")
                    if self.event_q:
                        self.event_q.put((self.approach, "audio", 0.9))
            time.sleep(0.5)
