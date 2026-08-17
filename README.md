# Project Aegis

Current version: **0.3 development prototype**

Project Aegis is an offline situational-awareness platform for detecting,
tracking, and assessing RF contacts. Version 1 is targeted for Raspberry Pi 4.

## Current capabilities

- Generate and load simulated RF spectrum data
- Estimate the noise floor and detection threshold
- Detect multiple signal regions
- Track contacts across scans
- Increase, decay, and expire contact confidence
- Reacquire temporarily missing contacts
- Run deterministic multi-scan scenarios without an SDR
- Display a lightweight native situational-awareness dashboard
- Receive live 1090 MHz ADS-B aircraft through an RTL-enabled `readsb`
- Plot measured aircraft positions over cached OpenStreetMap tiles

All bearings, locations, spectrum traces, and waterfall data in the current GUI
are simulated. The interface labels unavailable sensors as standby and does not
represent simulated data as real sensor output.

## Run the dashboard

From the repository root:

```powershell
python -m src.aegis.gui
```

Use **Start Sim** to load the fictional drone mission, then **Next** or **Play**
to advance it. **Record** saves the mission as structured event segments.
**Open** loads a recording for deterministic replay, and **Stop** closes an
active recording cleanly.

The included trajectory uses fictional coordinates. Distance, bearing, heading,
Remote ID, RF activity, spectrum, and waterfall content remain simulated.

## Run live ADS-B on Raspberry Pi

Build `readsb` with RTL-SDR support in `~/readsb-rtl`, then launch Aegis and
select **Live ADS-B**. Aegis starts the receiver locally, reads its JSON output
once per second, and stops it when the session or application closes.

```bash
cd ~/Aegis-19-40
python3 -m src.aegis.gui
```

Close Gqrx, `rtl_adsb`, and other SDR programs first. The online basemap uses
OpenStreetMap tiles and caches downloaded tiles under
`~/.cache/aegis/map_tiles`; receiver data is not uploaded by Aegis.

## Run the tests

```powershell
python -m unittest discover -v
```

## Version 1 target

Version 1 will run locally on a Raspberry Pi 4. The software is therefore being
designed around an offline-first native interface, low redraw frequency,
bounded memory use, modular sensor inputs, and no required cloud services.
