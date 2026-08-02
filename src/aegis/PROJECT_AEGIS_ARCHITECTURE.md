# Project Aegis Architecture

## Product target

Version 1 is a platform-independent, offline-capable RF situational-awareness
system. Raspberry Pi 4 is the first development and edge deployment target,
not an architectural ceiling. SDR and other hardware inputs will be added
behind stable software interfaces after the detection, tracking, and operator
workflows are proven with deterministic simulation.

## Layers

1. **Sources** provide spectrum frames or simulated detections.
2. **Detection** converts spectrum data into measured signal regions.
3. **Tracking** associates detections and manages the contact lifecycle.
4. **Snapshots** expose immutable contact state to consumers.
5. **Interface** renders status without owning detection or tracking logic.

The GUI currently consumes simulator snapshots. A future SDR source must feed
the same processing boundary so the dashboard does not require a redesign.

## Deployment profiles

- **Edge Lite:** Raspberry Pi-class Scout and Relay deployments
- **Edge Performance:** Higher-performance Tracker and Sentinel deployments
- **Air Node:** Size, weight, power, and thermal constrained deployment
- **Command:** Workstation-class aggregation, analysis, and storage

All profiles use the same versioned event, contact, and recording contracts.
Hardware acceleration and device access remain optional adapters.

## Edge constraints

- Lightweight native interface; no browser runtime required for core operation
- Canvas rendering without mandatory GPU acceleration
- Dashboard redraws on scan updates rather than continuously
- No network dependency for core operation
- Bounded scan and contact history
- Sensor modules must fail independently without taking down the dashboard
- Recorded input must remain available for repeatable testing

## Truthful-state rule

The interface must distinguish measured, inferred, simulated, unavailable, and
stale information. It must never display a simulated bearing or classification
as a real sensor result.

## Planned modules

- Versioned sensor-event and contact data contract
- Remote ID receiver and trajectory source
- SDR spectrum source
- Spectrum and waterfall history buffer
- Direction-finding source
- Contact classification and evidence engine
- Alert policy
- Recording and playback
- System-health monitoring
