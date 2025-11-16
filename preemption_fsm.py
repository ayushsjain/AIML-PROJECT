# preemption_fsm.py

class State:
    NORMAL = "normal"
    LATENCY = "latency"
    ACTIVE = "active"
    RECOVERY = "recovery"


class PreemptionFSM:
    def __init__(self, latency_ms=3000, max_hold_ms=15000, grace_ms=1500):
        self.state = State.NORMAL

        self.latency_ms = latency_ms
        self.max_hold_ms = max_hold_ms
        self.grace_ms = grace_ms

        self.timer = 0
        self.active_direction = None

    def update(self, dt_ms, detected_dir):
        """Update FSM state based on detections and timing."""

        if self.state == State.NORMAL:
            if detected_dir:
                self.state = State.LATENCY
                self.timer = 0
                self.active_direction = detected_dir

        elif self.state == State.LATENCY:
            self.timer += dt_ms
            if self.timer >= self.latency_ms:
                self.state = State.ACTIVE
                self.timer = 0

        elif self.state == State.ACTIVE:
            self.timer += dt_ms

            # if emergency disappears + grace passed → RECOVERY
            if not detected_dir and self.timer >= self.grace_ms:
                self.state = State.RECOVERY
                self.timer = 0

            # safety timer to prevent infinite lock
            if self.timer >= self.max_hold_ms:
                self.state = State.RECOVERY
                self.timer = 0

        elif self.state == State.RECOVERY:
            self.timer += dt_ms
            if self.timer >= self.latency_ms:
                self.state = State.NORMAL
                self.timer = 0
                self.active_direction = None

        return self.state, self.active_direction
