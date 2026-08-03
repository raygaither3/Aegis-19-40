# Aegis Structured Recording Format 1.0

A recording is a directory containing an atomic manifest and one or more
append-only JSON Lines event segments.

```text
recording-id/
|-- manifest.json
|-- segment-000001.jsonl
|-- segment-000002.jsonl
`-- segment-000003.jsonl
```

## Manifest

The manifest records the recording format version, event schema version,
recording and node identifiers, timestamps, recording status, event count, and
ordered segment list. It is replaced atomically when the recording state
changes or a segment is added.

Recording status is one of:

- `recording`
- `complete`
- `interrupted`

## Segments

Each nonblank line is one complete Sensor Event Schema 1.0 JSON object. Segments
are bounded by event count so an interrupted write cannot damage an entire
mission recording.

The reader offers two modes:

- Strict mode stops at the first missing, corrupt, or unsupported event.
- Recovery mode returns valid events in recorded order and reports every issue.

## Playback

Playback preserves file order. Speed `0` performs deterministic playback with
no waiting. Speed `1` preserves recorded timestamp spacing. Other positive
values scale that spacing.

## Scope

This format stores structured events. Raw IQ samples and dense spectrum frames
will use a separate binary data format referenced by structured events. They
must not be embedded directly into JSON Lines segments.
