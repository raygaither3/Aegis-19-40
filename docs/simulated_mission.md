# Simulated Drone Mission

The built-in mission is an end-to-end development source for Aegis. It emits a
fictional Remote ID trajectory and correlated RF detections through Sensor Event
Schema 1.0.

The pipeline is:

```text
Mission simulator
  -> versioned Remote ID and RF events
  -> optional segmented recording
  -> RF contact tracker
  -> immutable mission frames
  -> dashboard
```

The scenario contains ten one-second frames. One RF observation is omitted to
exercise contact fading and reacquisition while Remote ID remains available.

The observer and aircraft coordinates are fictional constants embedded in the
simulator. They are not derived from the host computer, network, or operator.

## Dashboard controls

- **Start Sim:** load a fresh fictional mission
- **Record:** choose a parent directory and record events while frames advance
- **Open:** load a recording directory in recovery mode
- **Stop:** stop playback and close an active recording cleanly
- **Play/Pause:** advance frames automatically
- **Next:** advance exactly one frame

Recorded and replayed missions use the same event-to-frame processing path as
the simulator. Replay therefore exercises event validation, tracking, geometry,
and visualization together.
