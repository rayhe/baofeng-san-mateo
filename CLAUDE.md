# CLAUDE.md

## Project Overview

Baofeng BF-F8HP radio programming files for Menlo Park, San Mateo County, and surrounding Bay Area public safety / utility frequencies. Programs the radio with a comprehensive set of local receivable frequencies using an FTDI USB programming cable.

This is a **receive-only / scanner** use case for public safety frequencies. Transmitting on licensed public safety frequencies without authorization is a federal crime.

## Repository Structure

```
frequencies.csv          # CHIRP-compatible CSV, 128 channels (0-127), ready to upload
flash_chirp.py           # CHIRP-driver-based flasher (working, preferred)
flash_radio.py           # Legacy standalone flasher (BUGGY — do not use, see below)
FREQUENCY_REFERENCE.txt  # Detailed human-readable reference with all frequencies, notes, sources
README.md                # Project description
chirp-src/               # CHIRP source checkout (git-ignored, clone separately)
```

## Hardware Setup

- **Radio**: Baofeng BF-F8HP (8W tri-power, also compatible with UV-5R, UV-82HP)
- **Cable**: FTDI USB programming cable (Baofeng/Kenwood 2-pin connector, FTDI VID:PID 0403:6001)
- **COM port**: COM3 (FTDI driver installs automatically on Windows 11)
- **Software**: `flash_chirp.py` (requires `pyserial` + CHIRP source checkout)

## Programming Workflow

### Prerequisites

```bash
pip install pyserial
git clone https://github.com/kk7ds/chirp.git chirp-src
```

### Flashing the radio (two-step process)

The radio must be power-cycled between download and upload — it drops out of clone mode after each serial session.

**Step 1: Download current image from radio**
```bash
python flash_chirp.py download [COM3]
```
This reads the radio's full memory into `radio_image.img` and saves a backup to `radio_backup.img`.

**Step 2: Power cycle the radio** (turn off, turn back on)

**Step 3: Upload channels to radio**
```bash
python flash_chirp.py upload [frequencies.csv] [COM3]
```
This loads the downloaded image, programs all 128 channels from the CSV using CHIRP's `set_memory()` API, then uploads the full image back to the radio.

**Step 4: Power cycle the radio again** to apply changes.

### Fixing settings after flash

If settings need adjustment (display mode, voice language, squelch, etc.), patch the image before uploading:

```python
import sys, os
sys.path.insert(0, "chirp-src")
from chirp.drivers import uv5r

radio = uv5r.BaofengBFF8HPRadio(None)
radio.load_mmap("radio_image.img")
s = radio._memobj.settings
s.voice = 1      # 0=Off, 1=English, 2=Chinese
s.mdfa = 2       # VFO A display: 0=Frequency, 1=Channel#, 2=Name
s.mdfb = 2       # VFO B display: 0=Frequency, 1=Channel#, 2=Name
s.squelch = 4    # 0-9
s.beep = 1       # 0=Off, 1=On
s.abr = 3        # Backlight timeout in seconds (0=off)
radio.save_mmap("radio_image.img")
```

Then re-run the upload step. The patched settings will be included in the upload.

### CHIRP GUI (alternative)

1. Connect BF-F8HP to PC via FTDI USB cable
2. Open CHIRP, go to Radio > Download From Radio
3. File > Import, select `frequencies.csv`
4. Select all channels, click OK
5. Radio > Upload To Radio

## flash_radio.py — KNOWN BUG, DO NOT USE

The legacy `flash_radio.py` has a critical 8-byte memory address offset bug. CHIRP's upload protocol uses `_send_block(radio, i - 0x08, ...)` — radio addresses are offset by -8 from image file offsets. The custom script writes to wrong addresses, shifting ALL data (channels, settings, names) by 8 bytes. Symptoms: Chinese language mode, unable to switch channels, corrupt channel names, work mode bytes invalid. Use `flash_chirp.py` instead.

## Supported Radios

The flash script uses CHIRP's `BaofengBFF8HPRadio` driver. UV-5R radios use the same protocol family but a different CHIRP driver class.

| | BF-F8HP | UV-5R |
|---|---|---|
| **Power levels** | 3 (High 8W / Mid 4W / Low 1W) | 2 (High 5W / Low 1W) |
| **Name length** | 7 characters | 6 characters |
| **Channels** | 128 (0-127) | 128 (0-127) |
| **Protocol** | UV-5R family (9600 8N1) | UV-5R family (9600 8N1) |
| **CHIRP driver** | `BaofengBFF8HPRadio` | `BaofengUV5RGeneric` |
| **Firmware ident** | `aa307604000520dd` | varies |

- All channels are set to lowest power (RX-only scanner use)
- CSV names are all 6 chars or less so the same file works for both radios
- To flash a UV-5R, change the driver class in `flash_chirp.py` from `BaofengBFF8HPRadio` to `BaofengUV5RGeneric`

## Channel Layout (128 channels, 0-127)

| Range   | Category                              | Band     |
|---------|---------------------------------------|----------|
| 0-2     | Local PD: Menlo Park, Atherton, EPA   | UHF      |
| 3-8     | San Mateo County Sheriff              | UHF      |
| 9-13    | Redwood City PD, Hillsborough PD      | UHF      |
| 14-18   | SMC Fire South (Menlo Park Fire)      | VHF      |
| 19-23   | SMC Fire Central                      | VHF      |
| 24-28   | SMC Fire North                        | VHF      |
| 29-37   | SMC Fire Coast + County Command       | VHF      |
| 38-44   | CalFire CZU                           | VHF      |
| 45-52   | CHP (reference only — out of range)   | Low Band |
| 53-56   | NOAA Weather                          | VHF      |
| 57-71   | National Interop (VTAC/VFIRE/VLAW/VMED)| VHF     |
| 72-80   | CA Mutual Aid (CLEMARS/CALCORD/White Fire)| Mixed |
| 81-84   | National Interop UHF (UCALL/UTAC)     | UHF      |
| 85-98   | FRS channels 1-14                     | UHF      |
| 99-106  | GMRS channels 15-22                   | UHF      |
| 107-111 | MURS channels 1-5                     | VHF      |
| 112-126 | Additional SMC PDs (Brisbane to HMB)  | UHF      |
| 127     | SAR (VSAR16/NATSAR)                   | VHF      |

## Baofeng Receiver Limitations

- **VHF range**: 136-174 MHz (fire dispatch, CalFire, interop, weather, MURS)
- **UHF range**: 400-520 MHz (police conventional, FRS/GMRS, UHF interop)
- **Cannot receive**: Low band VHF (<136 MHz, so CHP at 42 MHz is out), 700/800/900 MHz
- **Analog FM/NFM only**: Cannot decode P25 digital, DMR, trunking
- CHP channels (45-52) are included for reference but will not produce audio on a Baofeng

## CSV Format (CHIRP Standard)

Columns: `Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,DtcsCode,DtcsPolarity,Mode,TStep,Skip,Comment,URCALL,RPT1CALL,RPT2CALL,DVCODE`

- **Location**: Channel number (0-127)
- **Name**: 7-char max alpha tag (BF-F8HP) / 6-char on UV-5R
- **Frequency**: RX frequency in MHz
- **Tone**: `Tone` = TX CTCSS, `TSQL` = RX squelch, blank = none
- **Mode**: `FM` (25 kHz wide) or `NFM` (12.5 kHz narrow)
- **Comment**: Human-readable description (not stored on radio)

## Key Frequencies to Know

- **153.890 MHz** (Ch 14, SMCF-S1): Menlo Park Fire dispatch — most active local channel
- **488.3375 MHz** (Ch 0, MP-PD): Menlo Park PD dispatch
- **488.8875 MHz** (Ch 3, SMSO-GR): SMC Sheriff countywide green
- **162.400 MHz** (Ch 53, WX-SFBA): NOAA Weather for SF Bay Area
- **462.5625 MHz** (Ch 85, FRS-01): FRS Channel 1 (license-free)

## Editing Guidelines

- Hard limit of **128 memory channels** (0-127). The CSV is at capacity.
- To add a frequency, one must be removed or the file must be split into multiple profiles.
- Channel names: **7 chars** on BF-F8HP, **6 chars** on UV-5R (CHIRP enforces on upload).
- When editing `frequencies.csv`, keep the CHIRP CSV header row intact.
- Update `FREQUENCY_REFERENCE.txt` to match any CSV changes.
- Verify frequencies against RadioReference.com (radioreference.com/db/browse/ctid/223) — agencies occasionally migrate to P25 trunked systems, making analog channels go silent.

## Technical Notes

### CHIRP memory map (BF-F8HP / UV-5R family)
- **Channel data**: image offset 0x0008 (radio address 0x0000), 16 bytes per channel
- **Channel names**: image offset 0x1008, 16 bytes per name slot (7 usable chars on F8HP)
- **Settings**: image offset 0x0E28 (voice, display mode, squelch, beep, backlight, etc.)
- **Work mode**: image offset 0x0E7E-0x0E7F
- **Critical**: radio addresses = image offsets - 8. CHIRP's `_send_block()` does `addr = i - 0x08`.

### Serial protocol
- 9600 baud, 8N1, 1s timeout
- Magic byte handshake to enter clone mode
- Download: 0x40-byte blocks
- Upload: 0x10-byte blocks with checksum
- Radio must be power-cycled between download and upload sessions

## Sources

- RadioReference.com San Mateo County database
- W6AER San Mateo County frequency guide
- Broadcastify feeds for San Mateo County
- ScanCal.org CalFire frequencies
- NIFOG (National Interoperability Field Operations Guide)
- FCC Part 95 rules (FRS/GMRS/MURS)
- CHIRP source (github.com/kk7ds/chirp) — BF-F8HP driver in `chirp/drivers/uv5r.py`
