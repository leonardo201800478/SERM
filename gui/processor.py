import threading
import sys
from io import StringIO

class AsyncProcessor(threading.Thread):
    def __init__(self, target, args=(), kwargs=None, log_callback=None, progress_callback=None):
        super().__init__()
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.exception = None
        self.result = None
        self.daemon = True

    def run(self):
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            self.result = self.target(*self.args, **self.kwargs)
        except Exception as e:
            self.exception = e
            import traceback
            self.exception_traceback = traceback.format_exc()
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout
            if self.log_callback:
                self.log_callback(output)
            if self.progress_callback:
                self.progress_callback(100, "Concluído")