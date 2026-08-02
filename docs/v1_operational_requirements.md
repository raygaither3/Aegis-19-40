# Aegis v1 Operational Requirements

Status: **Working baseline**  
Last updated: 2026-08-01

This document defines what Aegis v1 must accomplish before hardware or
implementation choices are treated as final. Values marked **TBD** require an
explicit product decision or measured prototype result.

## 1. Mission

Aegis v1 shall provide authorized operators with local, offline-capable RF
situational awareness. It shall detect signal activity, maintain persistent
contacts, communicate confidence and data quality honestly, and preserve
evidence for later review.

Aegis v1 is the common software foundation for independently operated or
networked Scout, Tracker, Sentinel, Air Node, Relay, and Command deployments.

## 2. Product principles

1. **Truthful state:** measured, inferred, simulated, stale, and unavailable
   information must be visibly distinguishable.
2. **Platform independence:** core detection, tracking, storage, and event
   models must not depend on Raspberry Pi-specific APIs.
3. **Offline operation:** core monitoring must not require cloud services or an
   internet connection.
4. **Repeatability:** recorded inputs must be replayable for testing and
   analysis.
5. **Modularity:** sensors, compute acceleration, storage, positioning, and
   networking must be replaceable adapters.
6. **Fail-soft behavior:** loss of one sensor or network link must not crash the
   rest of the system.
7. **Authorized operation:** deployment must comply with applicable spectrum,
   privacy, recording, aviation, and location-specific rules.

## 3. Version 1 boundary

### Required for v1

- One local node operating without a network
- One replaceable SDR source, plus file and simulator sources
- Spectrum acquisition and waterfall history
- Signal-region detection
- Persistent contact tracking
- Confidence growth, decay, reacquisition, and expiration
- Contact list and contact-detail views
- Recording and deterministic playback
- Operator-visible sensor health and data provenance
- Exportable diagnostic logs
- Clean shutdown and recovery after interrupted operation

### Designed for, but not required for initial v1 acceptance

- Multiple cooperative nodes
- Direction-finding adapters
- GPS and time-source adapters
- Contact classification
- Alert policies
- Command-station aggregation
- Hardware acceleration

### Outside initial v1 acceptance

- Autonomous enforcement or response
- Unsupported claims of emitter identity or location
- Dependence on proprietary cloud services
- The complete illustrated hardware product family

## 4. Deployment profiles

| Profile | Intended role | Initial compute assumption | Core expectation |
|---|---|---|---|
| Edge Lite | Scout / Relay | Raspberry Pi-class | Detect, track, record, report |
| Edge Performance | Tracker / Sentinel | TBD higher-performance edge compute | Wider bandwidth, fusion, classification |
| Air Node | Airborne sensing | TBD SWaP-constrained compute | Acquire, record, report, relay |
| Command | Command Case | Workstation-class | Aggregate, visualize, store, coordinate |

Raspberry Pi 4 support is a deployment requirement for Edge Lite, not a limit
on the capabilities of other profiles.

## 5. Functional requirements

| ID | Requirement | v1 acceptance evidence |
|---|---|---|
| FR-001 | Accept simulator, recorded-file, and SDR input through a common source interface | Automated source-contract tests |
| FR-002 | Estimate noise floor and detect contiguous signal regions | Labeled-spectrum test corpus |
| FR-003 | Assign stable contact IDs across sequential scans | Tracker scenario tests |
| FR-004 | Represent tentative, confirmed, fading, and expired contact lifecycle states | Lifecycle tests and replay |
| FR-005 | Record source metadata, detections, contacts, and health events | Recording inspection and schema validation |
| FR-006 | Replay a recording deterministically without RF hardware | Replay result matches recorded result |
| FR-007 | Display spectrum, waterfall, active contacts, confidence, provenance, and sensor health | Operator workflow test |
| FR-008 | Label simulated, inferred, stale, and unavailable values | UI inspection and state tests |
| FR-009 | Continue local monitoring during network loss | Network-disconnect test |
| FR-010 | Recover safely from a source or sensor failure | Fault-injection test |
| FR-011 | Export logs without modifying the original recording | Hash comparison and export test |
| FR-012 | Use versioned event and recording schemas | Compatibility test across schema versions |

## 6. Performance decisions

These values must be chosen from the intended mission and then validated on
each deployment profile.

| ID | Measure | Edge Lite target | Edge Performance target | Decision basis |
|---|---|---:|---:|---|
| PR-001 | Tunable frequency range | TBD | TBD | SDR and intended signals |
| PR-002 | Instantaneous processed bandwidth | TBD | TBD | Mission and compute budget |
| PR-003 | Scan/update interval | TBD | TBD | Required detection latency |
| PR-004 | Detection latency | TBD | TBD | Operator workflow |
| PR-005 | Concurrent active contacts | TBD | TBD | Expected RF density |
| PR-006 | Maximum false-alarm rate | TBD | TBD | Labeled field recordings |
| PR-007 | Minimum detection probability | TBD | TBD | Labeled field recordings |
| PR-008 | Recording duration | TBD | TBD | Storage and mission duration |
| PR-009 | Startup-to-monitoring time | TBD | TBD | Field workflow |
| PR-010 | UI refresh rate | TBD | TBD | Readability and compute budget |
| PR-011 | Direction-finding accuracy | Not required initially | TBD | Hardware geometry and calibration |
| PR-012 | Classification accuracy | Not required initially | TBD | Labeled dataset and model |

No performance claim is considered satisfied solely because it works with the
current simulator.

## 7. Data requirements

Every sensor event and contact update shall be able to carry:

- Schema version
- Event ID
- Node ID and node type
- Sensor ID and sensor type
- UTC timestamp and monotonic sequence information
- Data provenance: measured, inferred, simulated, replayed, or unavailable
- Freshness or age
- Frequency and bandwidth measurements with units
- Power and noise measurements with units
- Optional position, bearing, and associated uncertainty
- Contact ID, lifecycle state, and confidence
- Evidence contributing to confidence
- Software version and configuration identity

Unknown values must be absent or explicitly unavailable, never silently zero.

## 8. Reliability and recovery

- Recordings shall be written in recoverable segments rather than one
  indefinitely open file.
- Configuration changes shall be logged.
- A source disconnect shall generate a health event and leave the interface
  responsive.
- A restarted process shall not present stale contacts as current.
- Resource use shall be bounded for continuous operation.
- Time discontinuities shall be detected and recorded.

## 9. Security and privacy

- Core operation shall remain local by default.
- Network listeners shall be disabled unless configured.
- Node identity and future inter-node messages shall support authentication.
- Recordings shall expose their origin and integrity status.
- Secrets shall not be stored in source code or ordinary recordings.
- Retention and export controls shall be configurable.

## 10. Operator-interface requirements

- Critical state must not depend on color alone.
- The interface shall show whether data is live, simulated, or replayed.
- Contact confidence shall expose supporting evidence, not only a percentage.
- Stale or unavailable sensors shall be visible without blocking healthy ones.
- The dashboard shall remain useful at 1280x720 and scale to larger command
  displays.
- Essential controls shall remain usable with keyboard and pointing device.

## 11. Acceptance gates

### Gate A: Software foundation

- Versioned event and contact model
- Deterministic serialization round trips
- Existing detector and tracker tests pass

### Gate B: Recording and playback

- Complete simulated session records successfully
- Replay produces matching contact history
- Interrupted recording remains recoverable

### Gate C: Edge Lite

- Raspberry Pi-class installation documented
- Sustained operation meets selected PR targets
- UI remains responsive during acquisition and recording

### Gate D: First SDR

- SDR adapter meets the common source contract
- Known test signals are detected and recorded
- Simulator and playback remain available without hardware

### Gate E: v1 field trial

- Selected operational requirements are measured in an authorized environment
- False alarms and misses are reviewed from recordings
- Failures produce actionable diagnostics

## 12. Decisions required from the product owner

The following answers establish the initial performance targets:

1. What types of authorized RF activity must v1 observe first?
2. What frequency range matters for the first field trial?
3. Is the first unit stationary, vehicle-mounted, portable, or all three?
4. How long must it operate per session and, if portable, on battery?
5. What is the maximum acceptable time from activity to operator notification?
6. Approximately how many simultaneous contacts should it handle?
7. Is recording raw spectrum required, or are processed measurements sufficient
   for the first version?
8. Must v1 operate without GPS or network time?
9. What display resolution and input method will the first field unit use?
10. Which outcome defines a successful first field demonstration?
