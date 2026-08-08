import threading
import sys

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
        self.stop_flag = False
        self.original_stdout = sys.stdout

    def stop(self):
        self.stop_flag = True

    def run(self):
        class Tee:
            def __init__(self, callback, original_stdout):
                self.callback = callback
                self.original_stdout = original_stdout

            def write(self, message):
                if message:
                    self.original_stdout.write(message)
                    self.original_stdout.flush()
                    if self.callback:
                        self.callback(message)

            def flush(self):
                self.original_stdout.flush()

        sys.stdout = Tee(self.log_callback, self.original_stdout)

        try:
            # Cria um objeto stop_flag que também carrega o callback
            stop_flag = self
            stop_flag.progress_callback = self.progress_callback
            self.kwargs['stop_flag'] = stop_flag
            self.result = self.target(*self.args, **self.kwargs)
        except Exception as e:
            self.exception = e
            import traceback
            self.exception_traceback = traceback.format_exc()
        finally:
            sys.stdout = self.original_stdout