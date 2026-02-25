# CLAUDE.md

## Project Overview

Baofeng radio programming files for Menlo Park, San Mateo County, and surrounding Bay Area public safety / utility frequencies. The goal is to program a Baofeng UV-5R (or compatible dual-band HT) with a comprehensive set of local receivable frequencies using CHIRP software and an FTDI USB programming cable.

This is a **receive-only / scanner** use case for public safety frequencies. Transmitting on licensed public safety frequencies without authorization is a federal crime.

## Repository Structure

```
frequencies.csv          # CHIRP-compatible CSV, 128 channels (0-127), ready to upload
FREQUENCY_REFERENCE.txt  # Detailed human-readable reference with all frequencies, notes, sources
README.md                # Project description
```

## Hardware Setup

- **Radio**: Baofeng UV-5R (or BF-F8HP, UV-82HP, UV-5R Plus)
- **Cable**: FTDI USB programming cable (Baofeng-compatible, often labeled "Kenwood 2-pin")
- **Software**: CHIRP (https://chirpmyradio.com) — free, open-source radio programming tool
- **Driver**: FTDI or Prolific USB-to-serial driver (Windows may auto-install; if not, install from FTDI website)

## Programming Workflow

1. Connect Baofeng to PC via FTDI USB cable (2-pin Kenwood connector into radio, USB into PC)
2. Open CHIRP, go to Radio > Download From Radio to pull current image
3. File > Import, select `frequencies.csv`
4. Select all channels, click OK
5. Radio > Upload To Radio to flash

The radio must be powered on and set to the correct COM port in CHIRP. Baud rate is typically 9600 for Baofeng radios.

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

- **Location**: Channel number (0-127 for UV-5R)
- **Name**: 6-char max alpha tag (UV-5R hardware limit)
- **Frequency**: RX frequency in MHz
- **Tone**: `Tone` = TX CTCSS, `TSQL` = RX squelch, blank = none
- **Mode**: `FM` (25 kHz wide) or `NFM` (12.5 kHz narrow)
- **Comment**: Human-readable description (not stored on radio)

## Key Frequencies to Know

- **153.890 MHz** (Ch 14, SMCF-S1A): Menlo Park Fire dispatch — most active local channel
- **488.3375 MHz** (Ch 0, MP-PD): Menlo Park PD dispatch
- **488.8875 MHz** (Ch 3, SMSO-GRN): SMC Sheriff countywide green
- **162.400 MHz** (Ch 53, WX-SFBA): NOAA Weather for SF Bay Area
- **462.5625 MHz** (Ch 85, FRS-01): FRS Channel 1 (license-free)

## Editing Guidelines

- The UV-5R has a hard limit of **128 memory channels** (0-127). The CSV is at capacity.
- To add a frequency, one must be removed or the file must be split into multiple profiles.
- Channel names are limited to **6 characters** on the UV-5R (CHIRP enforces this on upload).
- When editing `frequencies.csv`, keep the CHIRP CSV header row intact.
- Update `FREQUENCY_REFERENCE.txt` to match any CSV changes.
- Verify frequencies against RadioReference.com (radioreference.com/db/browse/ctid/223) — agencies occasionally migrate to P25 trunked systems, making analog channels go silent.

## Sources

- RadioReference.com San Mateo County database
- W6AER San Mateo County frequency guide
- Broadcastify feeds for San Mateo County
- ScanCal.org CalFire frequencies
- NIFOG (National Interoperability Field Operations Guide)
- FCC Part 95 rules (FRS/GMRS/MURS)
