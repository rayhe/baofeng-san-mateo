#!/usr/bin/env python3
"""
Flash Baofeng UV-5R with frequencies.csv via FTDI USB cable.

Protocol: 9600 8N1, no flow control.
Sequence: identify -> download current image -> patch channels -> upload.
"""

import csv
import struct
import sys
import time

import serial

PORT = "COM3"
BAUD = 9600
BLOCK_READ_SIZE = 0x40   # 64 bytes for reads
BLOCK_WRITE_SIZE = 0x10  # 16 bytes for writes

# Memory layout
CHAN_BASE = 0x0008        # 128 channels x 16 bytes
NAME_BASE = 0x1008        # 128 names x 16 bytes
MAIN_START = 0x0000
MAIN_END = 0x1808
AUX_START = 0x1EC0
AUX_END = 0x2000

# Upload ranges (skip calibration gaps)
UPLOAD_RANGES = [
    (0x0008, 0x0CF8),
    (0x0D08, 0x0DF8),
    (0x0E08, 0x1808),
]

# UV-5R identification magic (BFB291+ firmware)
MAGICS = [
    b"\x50\xBB\xFF\x20\x12\x07\x25",  # BFB291+
    b"\x50\xBB\xFF\x01\x25\x98\x4D",  # Original firmware
    b"\x50\xBB\xFF\x20\x13\x01\x05",  # UV-82
]

DTCS_CODES = [
     23,  25,  26,  31,  32,  36,  43,  47,  51,  53,
     54,  65,  71,  72,  73,  74, 114, 115, 116, 122,
    125, 131, 132, 134, 143, 145, 152, 155, 156, 162,
    165, 172, 174, 205, 212, 223, 225, 226, 243, 244,
    245, 246, 251, 252, 255, 261, 263, 265, 266, 271,
    274, 306, 311, 315, 325, 331, 332, 343, 346, 351,
    356, 364, 365, 371, 411, 412, 413, 423, 431, 432,
    445, 446, 452, 454, 455, 462, 464, 465, 466, 503,
    506, 516, 523, 526, 532, 546, 565, 606, 612, 624,
    627, 631, 632, 645, 654, 662, 664, 703, 712, 723,
    731, 732, 734, 743, 754,
]
NDCS = len(DTCS_CODES)


# --- Frequency encoding ---

def freq_to_bcd(freq_mhz):
    """Convert MHz float to 4-byte BCD (units of 10 Hz)."""
    freq_10hz = int(round(freq_mhz * 1e5))
    s = f"{freq_10hz:08d}"
    bcd = []
    for i in range(0, 8, 2):
        bcd.append((int(s[i]) << 4) | int(s[i + 1]))
    return bytes(bcd)


def bcd_to_freq(bcd_bytes):
    """Convert 4-byte BCD to MHz float."""
    digits = ""
    for b in bcd_bytes:
        digits += f"{(b >> 4) & 0x0F}{b & 0x0F}"
    return int(digits) * 10 / 1e6


# --- Tone encoding ---

def encode_tone(mode, row, direction):
    """Encode tone from CHIRP CSV fields. direction='tx' or 'rx'."""
    if mode == "Tone":
        if direction == "tx":
            return int(round(float(row["rToneFreq"]) * 10))
        return 0x0000
    elif mode == "TSQL":
        return int(round(float(row["cToneFreq"]) * 10))
    elif mode == "DTCS":
        code = int(row["DtcsCode"])
        pol = row.get("DtcsPolarity", "NN")
        p = pol[0] if direction == "tx" else pol[1]
        idx = DTCS_CODES.index(code)
        return (idx + 1) if p == "N" else (idx + 1 + NDCS)
    return 0x0000


# --- Serial protocol ---

def do_ident(ser):
    """Perform UV-5R handshake. Try multiple magic sequences."""
    for magic in MAGICS:
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        # Send magic one byte at a time
        for b in magic:
            ser.write(bytes([b]))
            time.sleep(0.01)

        ack = ser.read(1)
        if ack == b"\x06":
            # Send ident request
            ser.write(b"\x02")
            ident = ser.read(8)
            if len(ident) >= 8:
                ser.write(b"\x06")
                confirm = ser.read(1)
                if confirm == b"\x06":
                    ident_hex = ident.hex()
                    print(f"  Radio identified: {ident_hex}")
                    return ident
            # Try reading more bytes (some radios send 12)
            extra = ser.read(4)
            ident_full = ident + extra
            if len(ident_full) >= 8:
                ser.write(b"\x06")
                confirm = ser.read(1)
                if confirm == b"\x06":
                    print(f"  Radio identified (extended): {ident_full.hex()}")
                    return ident_full[:8]
        time.sleep(0.5)

    raise RuntimeError("Failed to identify radio. Check cable, power, and COM port.")


def read_block(ser, addr, size=BLOCK_READ_SIZE):
    """Read a block from radio memory."""
    cmd = struct.pack(">BHB", 0x53, addr, size)
    ser.write(cmd)

    header = ser.read(4)
    if len(header) < 4:
        raise RuntimeError(f"Short header at {addr:#06x}: got {len(header)} bytes")

    # Handle stale ACK
    if header[0:1] == b"\x06":
        header = header[1:] + ser.read(1)

    resp_cmd, resp_addr, resp_size = struct.unpack(">BHB", header)
    if resp_cmd != 0x58:
        raise RuntimeError(f"Bad response opcode at {addr:#06x}: {resp_cmd:#x}")

    data = ser.read(resp_size)
    if len(data) != resp_size:
        raise RuntimeError(f"Short data at {addr:#06x}: got {len(data)}/{resp_size}")

    ser.write(b"\x06")
    ser.read(1)  # ACK back
    time.sleep(0.05)
    return data


def write_block(ser, addr, data):
    """Write a 16-byte block to radio memory."""
    assert len(data) == BLOCK_WRITE_SIZE
    cmd = struct.pack(">BHB", 0x58, addr, len(data))
    ser.write(cmd)
    ser.write(data)

    ack = ser.read(1)
    if ack != b"\x06":
        raise RuntimeError(f"Write NAK at {addr:#06x}: {ack!r}")
    time.sleep(0.05)


# --- Download / Upload ---

def download_image(ser):
    """Download full memory image from radio."""
    image = bytearray(0x2000)

    # Main block
    total = (MAIN_END - MAIN_START) // BLOCK_READ_SIZE
    print(f"  Downloading main block ({total} reads)...")
    for i, addr in enumerate(range(MAIN_START, MAIN_END, BLOCK_READ_SIZE)):
        data = read_block(ser, addr, BLOCK_READ_SIZE)
        image[addr:addr + BLOCK_READ_SIZE] = data
        pct = (i + 1) * 100 // total
        print(f"\r  Main: {pct}% ({i+1}/{total})", end="", flush=True)
    print()

    # Aux block (use smaller reads for compatibility)
    total_aux = (AUX_END - AUX_START) // BLOCK_WRITE_SIZE
    print(f"  Downloading aux block ({total_aux} reads)...")
    for i, addr in enumerate(range(AUX_START, AUX_END, BLOCK_WRITE_SIZE)):
        data = read_block(ser, addr, BLOCK_WRITE_SIZE)
        image[addr:addr + BLOCK_WRITE_SIZE] = data
        pct = (i + 1) * 100 // total_aux
        print(f"\r  Aux: {pct}% ({i+1}/{total_aux})", end="", flush=True)
    print()

    return image


def upload_image(ser, image):
    """Upload patched image to radio (main block only, preserving settings)."""
    total_blocks = sum((end - start) // BLOCK_WRITE_SIZE for start, end in UPLOAD_RANGES)
    block_num = 0

    print(f"  Uploading {total_blocks} blocks...")
    for start, end in UPLOAD_RANGES:
        for addr in range(start, end, BLOCK_WRITE_SIZE):
            block = bytes(image[addr:addr + BLOCK_WRITE_SIZE])
            write_block(ser, addr, block)
            block_num += 1
            pct = block_num * 100 // total_blocks
            print(f"\r  Upload: {pct}% ({block_num}/{total_blocks})", end="", flush=True)
    print()


# --- CSV -> Image patching ---

def compute_tx_freq(rx_freq, duplex, offset):
    if duplex == "+":
        return rx_freq + offset
    elif duplex == "-":
        return rx_freq - offset
    elif duplex == "split":
        return offset
    elif duplex == "off":
        return rx_freq  # store same as RX, TX disabled by radio config
    return rx_freq  # simplex


def patch_channels(image, csv_path):
    """Read CSV and patch channel + name data into the image."""
    count = 0
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ch = int(row["Location"])
            if ch < 0 or ch > 127:
                print(f"  WARNING: skipping out-of-range channel {ch}")
                continue

            rx_freq = float(row["Frequency"])
            duplex = row.get("Duplex", "").strip()
            offset = float(row.get("Offset", "0.0"))
            tx_freq = compute_tx_freq(rx_freq, duplex, offset)

            rx_bcd = freq_to_bcd(rx_freq)
            tx_bcd = freq_to_bcd(tx_freq)

            tone_mode = row.get("Tone", "").strip()
            txtone = encode_tone(tone_mode, row, "tx")
            rxtone = encode_tone(tone_mode, row, "rx")

            is_uhf = 1 if rx_freq >= 400.0 else 0
            wide = 1 if row.get("Mode", "FM").strip() == "FM" else 0
            scan = 0 if row.get("Skip", "").strip() == "S" else 1

            # Build 16-byte channel entry
            ch_addr = CHAN_BASE + (ch * 16)
            image[ch_addr:ch_addr + 4] = rx_bcd
            image[ch_addr + 4:ch_addr + 8] = tx_bcd
            struct.pack_into("<H", image, ch_addr + 8, rxtone)
            struct.pack_into("<H", image, ch_addr + 10, txtone)
            image[ch_addr + 12] = (is_uhf << 4) & 0xFF  # flags1
            image[ch_addr + 13] = 0x00                    # flags2
            image[ch_addr + 14] = 0x00                    # flags3 (high power)
            image[ch_addr + 15] = ((wide & 1) << 6) | ((scan & 1) << 2)  # flags4

            # Build name entry
            name_addr = NAME_BASE + (ch * 16)
            name = row.get("Name", "")[:7].upper()
            name_bytes = bytearray(name.encode("ascii", errors="replace"))
            while len(name_bytes) < 7:
                name_bytes.append(0xFF)
            image[name_addr:name_addr + 7] = name_bytes[:7]
            image[name_addr + 7:name_addr + 16] = b"\xFF" * 9

            count += 1

    return count


# --- Main ---

def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "frequencies.csv"
    port = sys.argv[2] if len(sys.argv) > 2 else PORT

    print(f"=== Baofeng UV-5R Flash Tool ===")
    print(f"  CSV:  {csv_path}")
    print(f"  Port: {port}")
    print()

    ser = serial.Serial(port, baudrate=BAUD, bytesize=8, parity="N",
                        stopbits=1, timeout=1)
    try:
        # Step 1: Identify
        print("[1/4] Identifying radio...")
        do_ident(ser)
        print()

        # Step 2: Download current image
        print("[2/4] Downloading current image from radio...")
        image = download_image(ser)
        print()

        # Save backup
        backup_path = csv_path.replace(".csv", "_backup.img")
        with open(backup_path, "wb") as bf:
            bf.write(image)
        print(f"  Backup saved: {backup_path}")
        print()

        # Step 3: Patch channels from CSV
        print(f"[3/4] Patching channels from {csv_path}...")
        count = patch_channels(image, csv_path)
        print(f"  Patched {count} channels")
        print()

        # Step 4: Upload — reset serial line and re-identify
        print("[4/4] Uploading to radio...")
        # Toggle DTR to reset the radio's serial state
        ser.dtr = False
        time.sleep(0.5)
        ser.dtr = True
        time.sleep(0.5)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(1)
        do_ident(ser)
        upload_image(ser, image)
        print()

        print("=== DONE! Radio programmed with {0} channels. ===".format(count))
        print("Power cycle the radio to apply changes.")

    finally:
        ser.close()


if __name__ == "__main__":
    main()
