# Capture format (Pi → cloud)

> **Version 0.1-draft, agreed 2026-11-21** (PR #3, recorded in [decisions.md](decisions.md)). The Pi and cloud sides build against this. Propose changes in a PR.

Each capture is one JPEG plus one UTF-8 JSON file with the same stem:

```text
<device_id>/<YYYY-MM-DD>/<capture_id>.jpg
<device_id>/<YYYY-MM-DD>/<capture_id>.json
```

The date directory and the timestamp portion of `capture_id` use the device's UTC wall clock at capture, even when it is unsynced. Keep both paths stable across retries. The ID format is `<YYYYMMDDTHHMMSSmmmZ>_<sequence>`, such as `20261121T154210123Z_000412`. Write the sequence as a decimal integer padded to at least six digits. Persist the counter across reboots and advance it for every capture. Gaps are allowed. If the counter state is lost, provision a new unique `device_id` before capturing again.

For capture order on one device, compare the sequence suffix **numerically**, including across date directories. The filename's timestamp can sort out of order if the clock jumps. Use monotonic time for elapsed intervals within one boot only. Unsynced wall times cannot establish order across devices.

## Photo

- Save a full-resolution Camera Module 3 JPEG (4608 × 2592 pixels), quality 90 or higher, without resizing, cropping or filters on the Pi.
- Preserve camera-generated EXIF when present. Use the JSON sidecar for ingestion metadata.

## JSON metadata

The [sample JPEG](samples/20261121T154210123Z_000412.jpg) and [sample JSON](samples/20261121T154210123Z_000412.json) are a synthetic ingestion fixture. The image is a generated test pattern. Identifiers and timing are fixture values. GPS, orientation and mounting height are unmeasured. Pivot metadata is omitted to exercise the same contract for a tractor or bench capture.

```json
{
  "format_version": "0.1-draft",
  "capture_id": "20261121T154210123Z_000412",
  "device_id": "sample-cam-01",
  "field_id": "sample-field",
  "time": {
    "utc": "2026-11-21T15:42:10.123Z",
    "source": "unsynced",
    "boot_id": "00000000-0000-4000-8000-000000000001",
    "monotonic_ms": 31415926
  },
  "camera": {
    "tilt_deg": null,
    "tilt_source": "none",
    "roll_deg": null,
    "heading_deg": null,
    "height_m": null,
    "model": "camera-module-3",
    "lens": "standard",
    "resolution": [
      4608,
      2592
    ]
  },
  "gps": null
}
```

## Field rules

| Field | Required | Notes |
|---|---|---|
| `format_version`, `capture_id`, `device_id`, `field_id` | Yes | Use the draft version shown above. IDs are nonempty strings. `capture_id` matches both file stems, and `device_id` matches the device directory. |
| `time.utc`, `time.source` | Yes | UTC in ISO 8601 with milliseconds. Sources are `gps`, `ntp`, `rtc`, or `unsynced`. Use `unsynced` when the clock has no trusted time source. |
| `time.boot_id`, `time.monotonic_ms` | Yes | Stable boot identifier and nonnegative integer milliseconds since boot when the frame was captured. |
| `pivot`, `pivot_center` | Optional | Omit for mounts where pivot geometry does not apply. For pivot captures, include each value when available, or use `null` for missing measurements. |
| `pivot.angle_deg`, `pivot.angle_source` | If `pivot` is an object | Angle is clockwise from true north in [0, 360), or `null`. Source is `imu`, `encoder`, `gps`, or `none`. Use `none` with a null angle. GPS-derived angle requires a valid fix and known pivot center. |
| `pivot.camera_radius_m`, `pivot.pass_id` | Optional | Radius is the measured horizontal distance from the pivot center to the camera in meters. Pass ID groups frames from one sweep. |
| `pivot_center.lat`, `pivot_center.lon`, `pivot_center.source` | If `pivot_center` is an object | WGS 84 decimal degrees and a source of `configured` or `surveyed`. If the location is unknown, use `null` for the whole object or omit it. |
| `camera.model`, `camera.lens`, `camera.resolution` | Yes | Initial camera is `camera-module-3` with the `standard` lens. Resolution is `[width, height]` of the saved JPEG. |
| `camera.tilt_deg`, `camera.tilt_source` | Yes | Tilt is positive down from horizontal. Source is `installed` for a measured fixed angle, `imu` for a per-frame estimate, or `none` for `null` tilt. The planned 35° angle is not a measurement. |
| `camera.roll_deg`, `camera.heading_deg`, `camera.height_m` | Optional | Degrees for roll and heading, meters above ground for height. Positive roll is clockwise looking forward along the optical axis. Heading is clockwise from true north in [0, 360). Use `null` when unmeasured. |
| `camera.exposure_us`, `camera.analog_gain`, `camera.focus` | Optional | Copy reported exposure in microseconds, analog gain, and focus mode when available. |
| `gps` | Yes, nullable | Use `null` without a valid fix. With a fix, include `lat`, `lon` (WGS 84 decimal degrees), `fix` (`2d` or `3d`), and `source`. Include `alt_m` and `hdop` when reported. |
| `upload.attempt` | Optional | If emitted, this is the initial attempt number recorded when the sidecar is written. Track later retries in transfer logs. |

Use `null` for explicitly unmeasured values. Consumers should accept omitted optional fields and ignore unknown fields.

## Upload

1. Finish writing both local files to the SD card before queueing the pair. Keep the capture ID, paths and file contents stable across retries.
2. When known Wi-Fi is available, upload the JPEG first. Wait for the storage service to confirm that the complete JPEG was stored before publishing the JSON.
3. Ingestion uses the JSON as the ready marker, verifies its matching JPEG is present and readable, and deduplicates by `(device_id, capture_id)`. Repeating an upload with unchanged contents is safe. An existing key with different contents is a conflict to investigate.
4. Keep both local originals until the cloud confirms receipt of the pair. The specific storage API and acknowledgement mechanism are integration details for the Pi and cloud implementations.

## Relation to the older contract

[shared/capture-contract.md](../shared/capture-contract.md) describes the hackathon ESP32 camera posting to the local dashboard backend. This contract applies to the Pi. The backend can implement Pi ingestion after review.

## Proposed answers to the five open questions

1. **Pivot angle.** No source is selected for the first build. Record `null` and source `none` until a sensor or controller source is validated.
2. **GPS.** No module is selected. Record `gps: null` until a valid fix is available.
3. **Trigger.** Start with a configurable time interval. Set the cadence after testing capture throughput, vehicle speed and image overlap. Revisit angle triggering once angle telemetry is available.
4. **Connectivity.** Record locally during the pass and transfer when the Pi reaches known Wi-Fi. Field Wi-Fi availability and LTE are unconfirmed.
5. **Tilt.** Use a fixed mount for the first build. Record the measured installed angle when available. A moving mount would need a timestamped per-frame orientation estimate. No gimbal is selected.
