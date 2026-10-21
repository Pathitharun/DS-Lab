#!/usr/bin/env python3
"""
High-Performance Persistent Python Execution Server for DS Library
Provides instant (sub-10ms) code execution, state persistence across runs,
pandas DataFrame HTML rendering, and Matplotlib/Seaborn plot capture.
Also serves static web assets (HTML, CSS, JS, datasets).
"""

import sys
import os
import io
import ast
import json
import time
import base64
import traceback
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse

# Ensure matplotlib runs headlessly
os.environ["MPLBACKEND"] = "Agg"
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

try:
    import pandas as pd
except ImportError:
    pd = None

# Global persistent execution session
SESSION_NAMESPACE = {
    "__name__": "__main__",
    "__doc__": None,
}

# Pre-populate common data science imports for instant cell execution
INIT_SCRIPT = """
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
"""
try:
    exec(INIT_SCRIPT, SESSION_NAMESPACE)
    if plt is not None:
        plt.show = lambda *args, **kwargs: None
        SESSION_NAMESPACE["plt"] = plt
    if pd is not None:
        _orig_read_csv = pd.read_csv
        def _resilient_read_csv(filepath, *args, **kwargs):
            if isinstance(filepath, str) and "iris.csv" in filepath:
                local_iris = os.path.join(DIRECTORY, "iris.csv")
                if os.path.exists(local_iris):
                    try:
                        return _orig_read_csv(filepath, *args, **kwargs)
                    except Exception:
                        return _orig_read_csv(local_iris, *args, **kwargs)
            return _orig_read_csv(filepath, *args, **kwargs)
        pd.read_csv = _resilient_read_csv
        SESSION_NAMESPACE["pd"] = pd
except Exception as e:
    print(f"[WARN] Pre-import failed: {e}")

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))


def capture_plots():
    """Extracts all active matplotlib figures as base64 data URIs and closes them."""
    plots = []
    if plt is None:
        return plots
    try:
        fignums = plt.get_fignums()
        for fignum in fignums:
            fig = plt.figure(fignum)
            buf = io.BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight", dpi=130)
            buf.seek(0)
            b64_data = base64.b64encode(buf.read()).decode("ascii")
            plots.append(f"data:image/png;base64,{b64_data}")
            plt.close(fig)
        plt.close("all")
    except Exception as e:
        print(f"[WARN] Error capturing plots: {e}")
    return plots


def execute_python_code(code_str: str):
    """
    Executes Python code in the persistent SESSION_NAMESPACE.
    Returns: dict with stdout, result_repr, result_html, plots, execution_time_ms, success, error
    """
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = stdout_buf, stderr_buf

    start_time = time.perf_counter()
    result_repr = None
    result_html = None
    plots = []
    success = True
    error_msg = None

    try:
        # Parse abstract syntax tree to evaluate final expression like a notebook
        parsed = ast.parse(code_str)

        if not parsed.body:
            # Empty code
            pass
        elif isinstance(parsed.body[-1], ast.Expr):
            # Compile statements before the last expression
            last_expr = parsed.body.pop()
            if parsed.body:
                exec_mod = ast.Module(body=parsed.body, type_ignores=[])
                code_obj = compile(exec_mod, "<cell>", "exec")
                exec(code_obj, SESSION_NAMESPACE)

            # Evaluate final expression
            eval_mod = ast.Expression(body=last_expr.value)
            eval_code = compile(eval_mod, "<cell>", "eval")
            eval_res = eval(eval_code, SESSION_NAMESPACE)

            if eval_res is not None:
                if pd is not None and isinstance(eval_res, (pd.DataFrame, pd.Series)):
                    if isinstance(eval_res, pd.Series):
                        df_res = eval_res.to_frame()
                    else:
                        df_res = eval_res
                    result_html = df_res.to_html(classes="py-table", border=0, max_rows=100)
                    result_repr = str(eval_res)
                elif plt is not None and hasattr(eval_res, "figure"):
                    # Matplotlib axes or figure returned
                    result_repr = None
                else:
                    result_repr = repr(eval_res)
        else:
            code_obj = compile(parsed, "<cell>", "exec")
            exec(code_obj, SESSION_NAMESPACE)

        # Check for any figures generated during execution (plt.show(), plt.plot(), sns.pairplot(), etc.)
        plots = capture_plots()

    except Exception:
        success = False
        error_msg = traceback.format_exc()
        plots = capture_plots()
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
    captured_stdout = stdout_buf.getvalue()
    captured_stderr = stderr_buf.getvalue()

    # Filter out harmless headless Matplotlib warning
    cleaned_stderr_lines = [
        ln for ln in captured_stderr.splitlines()
        if "FigureCanvasAgg is non-interactive" not in ln
    ]
    cleaned_stderr = "\n".join(cleaned_stderr_lines).strip()

    full_stdout = captured_stdout.rstrip()
    if cleaned_stderr:
        full_stdout = (full_stdout + "\n" + cleaned_stderr).strip() if full_stdout else cleaned_stderr

    return {
        "success": success,
        "stdout": full_stdout,
        "result_repr": result_repr,
        "result_html": result_html,
        "plots": plots,
        "execution_time_ms": elapsed_ms,
        "error": error_msg,
    }


class DSRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        # Enable CORS for local development and iframe flexibility
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            status_payload = {
                "status": "ready",
                "backend": "native",
                "python_version": sys.version.split()[0],
                "platform": sys.platform,
                "has_pandas": pd is not None,
                "has_matplotlib": plt is not None,
            }
            self.wfile.write(json.dumps(status_payload).encode("utf-8"))
            return

        # Fallback to standard static file server
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/run":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            try:
                payload = json.loads(body)
                code = payload.get("code", "")
                if payload.get("reset", False):
                    SESSION_NAMESPACE.clear()
                    SESSION_NAMESPACE.update({"__name__": "__main__", "__doc__": None})
                    exec(INIT_SCRIPT, SESSION_NAMESPACE)

                output = execute_python_code(code)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(output).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
            return

        elif parsed.path == "/api/reset":
            SESSION_NAMESPACE.clear()
            SESSION_NAMESPACE.update({"__name__": "__main__", "__doc__": None})
            exec(INIT_SCRIPT, SESSION_NAMESPACE)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "reset_complete"}).encode("utf-8"))
            return

        self.send_error(404, "API endpoint not found")


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True


def run_server():
    server_address = ("", PORT)
    httpd = ReusableHTTPServer(server_address, DSRequestHandler)
    print(f"🚀 DS Library Native Python Server running at http://localhost:{PORT}/")
    print(f"⚡ Persistent Python execution active on {sys.version.split()[0]}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
