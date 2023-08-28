import threading
import time
from typing import Callable

class LoopThread(threading.Thread):
    """Thread subclass that runs a target function until `stop()` is called.

    Also facilitates the propagation of exceptions to the main thread.

    Args:
        target_function: The function to be run in the thread.

    Attributes:
        target_function: The function to be run in the thread.
        stop_signal: An event that can be set to signal the
            thread to stop.
        exc: Variable that is set to propagate an exception to the main thread.
    """

    def __init__(self, target_function: Callable[[], None], interval: float):
        super().__init__()
        self.target_function = target_function
        self.stop_signal = threading.Event()
        self.interval = interval
        self.exc = None

    def run(self):
        """Run the target function in a loop until the stop signal is set."""
        try:
            while not self.stop_signal.is_set():
                self.target_function()
                time.sleep(self.interval)
        except Exception as e:
            self.exc = e

    def stop(self):
        """Set the stop signal to stop the thread."""
        self.stop_signal.set()
        self.join()
        if self.exc:
            raise self.exc

    def propagate_exception(self):
        """Raises an exception if the target function raised an exception."""
        if self.exc:
            raise self.exc
