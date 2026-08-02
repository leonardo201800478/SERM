import threading
import sys
import time

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
        """Solicita a parada da execução."""
        self.stop_flag = True

    def run(self):
        # Cria um objeto que redireciona stdout para o callback e para o terminal
        class Tee:
            def __init__(self, callback, original_stdout):
                self.callback = callback
                self.original_stdout = original_stdout
                self.buffer = ""

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
            # Passa a flag de parada como argumento opcional
            if 'stop_flag' not in self.kwargs:
                self.kwargs['stop_flag'] = self
            self.result = self.target(*self.args, **self.kwargs)
        except Exception as e:
            self.exception = e
            import traceback
            self.exception_traceback = traceback.format_exc()
        finally:
            sys.stdout = self.original_stdout