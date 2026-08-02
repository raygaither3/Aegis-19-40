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

All bearings, locations, spectrum traces, and waterfall data in the current GUI
are simulated. The interface labels unavailable sensors as standby and does not
represent simulated data as real sensor output.

## Run the dashboard

From the repository root:

```powershell
python -m src.aegis.gui
```

Use **Next Scan** to step through the scenario or **Auto Play** to run all scans.

## Run the tests

```powershell
python -m unittest discover -v
```

## Version 1 target

Version 1 will run locally on a Raspberry Pi 4. The software is therefore being
designed around an offline-first native interface, low redraw frequency,
bounded memory use, modular sensor inputs, and no required cloud services.
