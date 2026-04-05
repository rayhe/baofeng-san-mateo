#!/usr/bin/env python3
"""Send CW (Morse code) via Digirig Mobile + Baofeng radio.

Usage:
    python send_cw.py [message] [--wpm 25] [--tone 700] [--port COM4] [--audio-index 11]

Examples:
    python send_cw.py WSLY991
    python send_cw.py "WSLY991 CQ CQ" --wpm 20
    python send_cw.py WSLY991 --wpm 30 --tone 800

Requires:
    - Digirig Mobile connected via USB (audio + serial)
    - CP210x driver installed for PTT serial port
    - Baofeng radio connected to Digirig via Baofeng cable
    - Radio tuned to desired channel
    - pip install pyaudio pyserial
"""

import argparse
import math
import struct
import time

import pyaudio
import serial

MORSE = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.',
    'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
    'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.',
    'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
    'Y': '-.--', 'Z': '--..', '0': '-----', '1': '.----', '2': '..---',
    '3': '...--', '4': '....-', '5': '.....', '6': '-....', '7': '--...',
    '8': '---..', '9': '----.', '/': '-..-.', ' ': ' '
}

SAMPLE_RATE = 44100


def generate_tone(duration, freq):
    samples = int(SAMPLE_RATE * duration)
    buf = b''
    for i in range(samples):
        val = int(32767 * 0.8 * math.sin(2 * math.pi * freq * i / SAMPLE_RATE))
        buf += struct.pack('<h', val)
    return buf


def generate_silence(duration):
    samples = int(SAMPLE_RATE * duration)
    return b'\x00\x00' * samples


def build_cw_audio(message, wpm, tone_hz):
    dot = 1.2 / wpm
    audio = b''
    for char in message.upper():
        if char == ' ':
            audio += generate_silence(dot * 7)
            continue
        code = MORSE.get(char, '')
        if not code:
            continue
        for j, symbol in enumerate(code):
            if symbol == '.':
                audio += generate_tone(dot, tone_hz)
            elif symbol == '-':
                audio += generate_tone(dot * 3, tone_hz)
            if j < len(code) - 1:
                audio += generate_silence(dot)
        audio += generate_silence(dot * 3)
    return audio


def send_cw(message, wpm=25, tone_hz=700, serial_port='COM4', audio_index=11):
    audio_data = build_cw_audio(message, wpm, tone_hz) + generate_silence(0.15)
    duration = len(audio_data) / 2 / SAMPLE_RATE
    print(f'{message} @ {tone_hz}Hz {wpm}WPM, {duration:.1f}s')

    ser = serial.Serial(serial_port, baudrate=9600, timeout=1)
    ser.rts = False
    ser.dtr = False
    time.sleep(0.1)

    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE,
                    output=True, output_device_index=audio_index)

    print('Keying PTT...')
    ser.rts = True
    time.sleep(0.4)

    print(f'Sending: {message}')
    stream.write(audio_data)
    time.sleep(0.1)

    ser.rts = False
    print('PTT released.')

    stream.stop_stream()
    stream.close()
    p.terminate()
    ser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Send CW via Digirig + Baofeng')
    parser.add_argument('message', nargs='?', default='WSLY991', help='Message to send (default: WSLY991)')
    parser.add_argument('--wpm', type=int, default=25, help='Words per minute (default: 25)')
    parser.add_argument('--tone', type=int, default=700, help='Tone frequency in Hz (default: 700)')
    parser.add_argument('--port', default='COM4', help='Digirig serial port (default: COM4)')
    parser.add_argument('--audio-index', type=int, default=11, help='PyAudio output device index (default: 11)')
    args = parser.parse_args()
    send_cw(args.message, args.wpm, args.tone, args.port, args.audio_index)
