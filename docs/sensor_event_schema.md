# Aegis Sensor Event Schema 1.0

The sensor event is the hardware-independent boundary between Aegis sources and
downstream processing, recording, networking, and visualization.

## Envelope

Every event contains:

- `schema_version`
- UUID `event_id`
- `event_type`
- `node_id` and `node_type`
- `sensor_id` and `sensor_type`
- timezone-aware `observed_at`
- monotonic per-sensor `sequence_number`
- `provenance`
- `data_state`
- typed `payload`

Unknown information is represented as absent or unavailable. It is never
silently replaced with zero.

## Provenance

- `measured`: produced directly by a physical sensor
- `inferred`: calculated or classified from other evidence
- `simulated`: produced by a deterministic or synthetic source
- `replayed`: read from an Aegis recording

## Data state

- `current`
- `stale`
- `unavailable`
- `invalid`

Provenance answers where data came from. Data state answers whether it is usable
now. These are intentionally separate.

## Initial payload types

### RF detection

Contains center frequency, bandwidth, peak power, and noise floor. It can be
emitted by SDR and simulator sensors.

### Remote ID observation

Contains the reported aircraft identifier and position, with optional speed,
heading, position accuracy, altitude, and operator position. Receiving a Remote
ID observation does not independently establish the legal identity or intent of
an operator.

### Sensor health

Contains healthy, degraded, failed, or offline status and an optional message.

## Compatibility policy

Readers reject unsupported major schema versions rather than silently
misinterpreting them. Schema migrations will be explicit and tested before a
new version is accepted for recording or networking.
