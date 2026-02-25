#!/usr/bin/env python3
"""
Flash BF-F8HP using CHIRP's actual driver. No homebrew protocol code.

Two-step process (radio must be power-cycled between steps):
  Step 1: python flash_chirp.py download   -> downloads image, saves backup
  Step 2: python flash_chirp.py upload     -> programs CSV channels and uploads

Usage:
  python flash_chirp.py download [COM3]
  python flash_chirp.py upload [frequencies.csv] [COM3]
"""

import csv
import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "chirp-src"))

from chirp.drivers import uv5r
from chirp import chirp_common, errors
import serial

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

PORT = "COM3"
IMAGE_FILE = "radio_image.img"


def status_cb(status):
    print(f"\r  {status.msg} {status.cur}/{status.max}", end="", flush=True)


def do_download(port):
    """Download image from radio and save to file."""
    print(f"[DOWNLOAD] Reading radio on {port}...")
    ser = serial.Serial(port, baudrate=9600, bytesize=8, parity="N",
                        stopbits=1, timeout=1)
    radio = uv5r.BaofengBFF8HPRadio(ser)
    radio.status_fn = status_cb

    radio.sync_in()
    print()

    radio.save_mmap(IMAGE_FILE)
    print(f"  Saved: {IMAGE_FILE}")

    # Also save a pristine backup
    radio.save_mmap("radio_backup.img")
    print(f"  Backup: radio_backup.img")

    ser.close()
    print("\n  Done! Now:")
    print("  1. Power cycle the radio (off then on)")
    print("  2. Run: python flash_chirp.py upload")


def do_upload(csv_path, port):
    """Load saved image, program channels from CSV, upload to radio."""
    if not os.path.exists(IMAGE_FILE):
        print(f"ERROR: {IMAGE_FILE} not found. Run 'download' first.")
        sys.exit(1)

    print(f"[UPLOAD] Loading {IMAGE_FILE}...")
    ser = serial.Serial(port, baudrate=9600, bytesize=8, parity="N",
                        stopbits=1, timeout=1)
    radio = uv5r.BaofengBFF8HPRadio(ser)
    radio.status_fn = status_cb

    # Load the downloaded image
    radio.load_mmap(IMAGE_FILE)

    # Program channels from CSV
    print(f"  Programming channels from {csv_path}...")
    count = 0
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ch_num = int(row["Location"])
            if ch_num < 0 or ch_num > 127:
                continue

            mem = chirp_common.Memory()
            mem.number = ch_num
            mem.name = row.get("Name", "")[:7].upper()
            mem.freq = int(float(row["Frequency"]) * 1000000)

            duplex = row.get("Duplex", "").strip()
            offset = float(row.get("Offset", "0.0"))
            mem.duplex = duplex if duplex else ""
            mem.offset = int(offset * 1000000)

            tone_mode = row.get("Tone", "").strip()
            if tone_mode == "Tone":
                mem.tmode = "Tone"
                mem.rtone = float(row.get("rToneFreq", "88.5"))
            elif tone_mode == "TSQL":
                mem.tmode = "TSQL"
                mem.ctone = float(row.get("cToneFreq", "88.5"))
            elif tone_mode == "DTCS":
                mem.tmode = "DTCS"
                mem.dtcs = int(row.get("DtcsCode", "23"))
                mem.dtcs_polarity = row.get("DtcsPolarity", "NN")
            else:
                mem.tmode = ""

            mem.mode = row.get("Mode", "FM").strip()
            mem.power = chirp_common.PowerLevel("Low", watts=1)
            skip = row.get("Skip", "").strip()
            mem.skip = skip if skip else ""
            mem.comment = row.get("Comment", "")

            try:
                radio.set_memory(mem)
                count += 1
            except Exception as e:
                print(f"\n  WARNING: Ch {ch_num}: {e}")

    print(f"  {count} channels programmed into image")

    # Upload to radio
    print(f"\n  Uploading to radio...")
    radio.sync_out()
    print()

    ser.close()
    print(f"\n=== DONE! {count} channels written. Power cycle the radio. ===")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python flash_chirp.py download [COM3]")
        print("  python flash_chirp.py upload [frequencies.csv] [COM3]")
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "download":
        port = sys.argv[2] if len(sys.argv) > 2 else PORT
        do_download(port)
    elif cmd == "upload":
        csv_path = sys.argv[2] if len(sys.argv) > 2 else "frequencies.csv"
        port = sys.argv[3] if len(sys.argv) > 3 else PORT
        do_upload(csv_path, port)
    else:
        print(f"Unknown command: {cmd}")
        print("Use 'download' or 'upload'")
        sys.exit(1)


if __name__ == "__main__":
    main()
