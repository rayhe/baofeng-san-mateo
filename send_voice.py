#!/usr/bin/env python3
"""Send voice message via Digirig Mobile + Baofeng radio using edge-tts neural voices.

Usage:
    python send_voice.py [message] [--voice en-US-JennyNeural] [--rate +20%] [--port COM4] [--audio-index 11]

Examples:
    python send_voice.py                                      # Default: WSLY991 + current time
    python send_voice.py "CQ CQ CQ this is Whiskey Sierra Lima Yankee 9 9 1"
    python send_voice.py "hello" --voice en-US-GuyNeural      # Male voice
    python send_voice.py --rate +30%                          # Faster speech

Voices:
    en-US-JennyNeural   (female, default)
    en-US-GuyNeural     (male)
    en-US-AriaNeural    (female)
    en-US-DavisNeural   (male)
    Run: edge-tts --list-voices | grep en-US   for full list

Requires:
    - Digirig Mobile connected via USB (audio + serial)
    - CP210x driver installed for PTT serial port
    - Baofeng radio connected to Digirig via Baofeng cable
    - Radio tuned to desired channel
    - pip install edge-tts pyaudio pyserial soundfile numpy
"""

import argparse
import asyncio
import datetime
import os
import tempfile
import time

import numpy as np
import pyaudio
import serial
import soundfile as sf

SAMPLE_RATE = 44100


async def generate_tts(message, voice, rate):
    import edge_tts

    tmp = os.path.join(tempfile.gettempdir(), 'digirig_tts.mp3')
    comm = edge_tts.Communicate(message, voice, rate=rate)
    await comm.save(tmp)

    data, samplerate = sf.read(tmp, dtype='int16')

    if len(data.shape) > 1:
        data = data.mean(axis=1).astype(np.int16)

    if samplerate != SAMPLE_RATE:
        indices = np.round(np.linspace(0, len(data) - 1,
                                       int(len(data) * SAMPLE_RATE / samplerate))).astype(int)
        data = data[indices]

    return data.astype(np.int16).tobytes()


def transmit(pcm, serial_port, audio_index):
    tail = b'\x00\x00' * int(SAMPLE_RATE * 0.15)
    audio_data = pcm + tail

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

    print('Transmitting...')
    stream.write(audio_data)
    time.sleep(0.1)

    ser.rts = False
    print('PTT released.')

    stream.stop_stream()
    stream.close()
    p.terminate()
    ser.close()


def default_message():
    now = datetime.datetime.now()
    time_str = now.strftime('%I %M %p').lstrip('0')
    return f'Whiskey Sierra Lima Yankee 9 9 1. The time is {time_str}.'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Send voice via Digirig + Baofeng')
    parser.add_argument('message', nargs='?', default=None,
                        help='Message to speak (default: WSLY991 + current time)')
    parser.add_argument('--voice', default='en-US-JennyNeural',
                        help='Edge TTS voice (default: en-US-JennyNeural)')
    parser.add_argument('--rate', default='+20%',
                        help='Speech rate adjustment (default: +20%%)')
    parser.add_argument('--port', default='COM4',
                        help='Digirig serial port (default: COM4)')
    parser.add_argument('--audio-index', type=int, default=11,
                        help='PyAudio output device index (default: 11)')
    args = parser.parse_args()

    message = args.message or default_message()
    print(f'Message: {message}')

    pcm = asyncio.run(generate_tts(message, args.voice, args.rate))
    dur = len(pcm) / 2 / SAMPLE_RATE
    print(f'Audio: {dur:.1f}s, voice={args.voice}, rate={args.rate}')

    transmit(pcm, args.port, args.audio_index)
