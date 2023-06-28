import threading
import time
from typing import Callable

class StoppableThread(threading.Thread):
    """Thread subclass that runs a target function until `stop()` is called.

    Args:
        target_function: The function to be run in the thread.

    Attributes:
        target_function (Callable): The function to be run in the thread.
        stop_signal (threading.Event): An event that can be set to signal the
            thread to stop.
    """

    def __init__(self, target_function: Callable[[], None], interval: float):
        super().__init__()
        self.target_function = target_function
        self.stop_signal = threading.Event()
        self.interval = interval

    def run(self):
        """Run the target function in a loop until the stop signal is set."""
        while not self.stop_signal.is_set():
            self.target_function()
            time.sleep(self.interval)

    def stop(self):
        """Set the stop signal to stop the thread."""
        self.stop_signal.set()

