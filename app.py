from flask import Flask, jsonify, render_template
import csv
import os
import threading
from datetime import datetime

import psutil

app = Flask(__name__)

LOG_FILE = "traffic_log.csv"
lock = threading.Lock()

previous = psutil.net_io_counters()

record_count = 0
anomaly_count = 0

# Create the CSV file and its header if needed.
if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
    with open(LOG_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            "timestamp",
            "upload_kib_s",
            "download_kib_s",
            "total_sent_bytes",
            "total_received_bytes",
            "packets_sent",
            "packets_received",
            "status",
        ])


@app.route("/")
def dashboard():
    return render_template("index.html")


@app.route("/api/traffic")
def traffic():
    global previous, record_count, anomaly_count

    with lock:
        current = psutil.net_io_counters()

        # Handle counter resets without reporting negative traffic.
        sent_delta = max(0, current.bytes_sent - previous.bytes_sent)
        recv_delta = max(0, current.bytes_recv - previous.bytes_recv)

        upload = round(sent_delta / 1024, 2)
        download = round(recv_delta / 1024, 2)

        # Convert to per-second rates using the time between samples.
        # The first request establishes a baseline.
        elapsed = 3.0
        if record_count == 0:
            upload_rate = 0.0
            download_rate = 0.0
        else:
            upload_rate = round(upload / elapsed, 2)
            download_rate = round(download / elapsed, 2)

        # Keep rates non-negative.
        total_rate = upload_rate + download_rate
        status = "High traffic" if total_rate > 1024 else "Normal"

        if status == "High traffic":
            anomaly_count += 1

        previous = current
        record_count += 1

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        sample = {
            "timestamp": timestamp,
            "upload_kbps": upload_rate,
            "download_kbps": download_rate,
            "total_sent_mb": round(current.bytes_sent / (1024 ** 2), 2),
            "total_received_mb": round(current.bytes_recv / (1024 ** 2), 2),
            "packets_sent": current.packets_sent,
            "packets_received": current.packets_recv,
            "traffic_volume_mb": round(
                (current.bytes_sent + current.bytes_recv) / (1024 ** 2), 2
            ),
            "record_count": record_count,
            "anomaly_count": anomaly_count,
            "status": status,
        }

        with open(LOG_FILE, "a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow([
                timestamp,
                upload_rate,
                download_rate,
                current.bytes_sent,
                current.bytes_recv,
                current.packets_sent,
                current.packets_recv,
                status,
            ])

        return jsonify(sample)


if __name__ == "__main__":
    app.run(debug=True)