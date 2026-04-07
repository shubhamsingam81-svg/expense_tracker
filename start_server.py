"""
╔══════════════════════════════════════════════════════╗
║        EXPENSE TRACKER — Local Server Launcher       ║
║                                                      ║
║  This starts a local web server so you can access    ║
║  the app from your iPhone on the same WiFi network.  ║
║                                                      ║
║  STEPS:                                              ║
║  1. Run this script: double-click or run in terminal ║
║  2. Open the URL shown on your iPhone's Safari       ║
║  3. Tap Share → "Add to Home Screen"                 ║
║  4. The app icon appears on your iPhone like an app! ║
║                                                      ║
║  Press Ctrl+C to stop the server.                    ║
╚══════════════════════════════════════════════════════╝
"""

import http.server
import socket
import os
import webbrowser

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def log_message(self, format, *args):
        # Cleaner logging
        print(f"  [{self.log_date_time_string()}] {format % args}")

    def end_headers(self):
        # Add headers needed for PWA
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Service-Worker-Allowed', '/')
        super().end_headers()


def get_local_ip():
    """Get the machine's local WiFi IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


if __name__ == "__main__":
    local_ip = get_local_ip()

    print()
    print("  ╔══════════════════════════════════════════════════╗")
    print("  ║         💰 EXPENSE TRACKER SERVER 💰            ║")
    print("  ╠══════════════════════════════════════════════════╣")
    print(f"  ║                                                  ║")
    print(f"  ║  Local:   http://localhost:{PORT}                 ║")
    print(f"  ║  Network: http://{local_ip}:{PORT}          ║")
    print(f"  ║                                                  ║")
    print("  ║  📱 Open the Network URL on your iPhone Safari   ║")
    print("  ║  📌 Then: Share → Add to Home Screen             ║")
    print(f"  ║                                                  ║")
    print("  ║  Press Ctrl+C to stop                            ║")
    print("  ╚══════════════════════════════════════════════════╝")
    print()

    # Open in browser on this PC too
    webbrowser.open(f"http://localhost:{PORT}")

    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped. Goodbye!")
        server.server_close()
