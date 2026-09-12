"""
AgriScan 360 - Flask IoT Web Dashboard Module
Broadcasts real-time inspection results and status over local Wi-Fi.
Satisfies the CSE 4326 IoT / Wireless Communication requirement.
"""

import threading
from flask import Flask, jsonify, render_template_string
from config import WEB_PORT

app = Flask("AgriScan360_IoT")

# In-memory latest scan record
latest_scan = {
    "produce": "None",
    "status": "IDLE - READY TO SCAN",
    "confidence": 0.0,
    "gas_delta_kohm": 0.0,
    "reason": "System initialized and waiting for scan cycle.",
    "timestamp": "N/A"
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AgriScan 360 - IoT Dashboard</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0e1117; color: #fff; text-align: center; padding: 25px; }
        .card { background: #1a1f2c; border: 1px solid #2d3748; border-radius: 12px; padding: 25px; max-width: 650px; margin: 0 auto; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        h1 { color: #00e5ff; margin-bottom: 5px; }
        .badge { font-size: 26px; font-weight: bold; padding: 10px 24px; border-radius: 8px; display: inline-block; margin: 15px 0; }
        .HEALTHY { background: #00c853; color: #000; }
        .ROTTEN  { background: #ff1744; color: #fff; }
        .UNCERTAIN { background: #ffd600; color: #000; }
        .IDLE { background: #4a5568; color: #fff; }
        .metric-box { display: flex; justify-content: space-around; margin-top: 20px; }
        .metric { background: #131722; padding: 15px; border-radius: 8px; flex: 1; margin: 0 8px; }
        .metric h3 { margin: 0; color: #90caf9; font-size: 14px; }
        .metric p { margin: 8px 0 0 0; font-size: 22px; font-weight: bold; }
        .reason { color: #b0bec5; font-style: italic; margin-top: 20px; font-size: 14px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>AgriScan 360</h1>
        <p style="color:#888;">Multi-Spectral Fruit & Vegetable Quality Station (UIU CSE 4326)</p>
        <hr style="border: 0; border-top: 1px solid #333; margin: 20px 0;">

        <h2>{{ data.produce.upper() }}</h2>
        <div class="badge {{ 'HEALTHY' if 'HEALTHY' in data.status else ('ROTTEN' if 'ROTTEN' in data.status else ('UNCERTAIN' if 'UNCERTAIN' in data.status else 'IDLE')) }}">
            {{ data.status }}
        </div>

        <div class="metric-box">
            <div class="metric">
                <h3>CONFIDENCE</h3>
                <p>{{ data.confidence }}%</p>
            </div>
            <div class="metric">
                <h3>GAS DELTA (ΔG)</h3>
                <p>{{ data.gas_delta_kohm }} kΩ</p>
            </div>
        </div>

        <p class="reason">Analysis: {{ data.reason }}</p>
        <p style="color:#555; font-size:12px; margin-top:20px;">Last Scan Time: {{ data.timestamp }}</p>
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE, data=latest_scan)

@app.route("/api/result")
def api_result():
    return jsonify(latest_scan)


def update_web_result(result_dict):
    """Updates the live dashboard state with new scan results."""
    global latest_scan
    latest_scan.update(result_dict)


def start_server_background():
    """Starts the Flask server in an asynchronous daemon thread."""
    t = threading.Thread(target=lambda: app.run(host="0.0.0.0", port=WEB_PORT, debug=False, use_reloader=False))
    t.daemon = True
    t.start()
    print(f"[IoT Web Server] Live at: http://0.0.0.0:{WEB_PORT} (View on your phone/laptop on same Wi-Fi)")
