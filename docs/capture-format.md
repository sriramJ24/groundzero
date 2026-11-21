# Capture format (Pi → cloud)

> **DRAFT.** Written by Sriram's side as a starting point. Tushar owns the Pi and should propose changes in a PR against this file. Nothing here is final until Tushar approves it, and the decision is recorded in [decisions.md](decisions.md).

Each capture is **one photo plus one JSON file with the same name**:

```
<device_id>/<YYYY-MM-DD>/<capture_id>.jpg
<device_id>/<YYYY-MM-DD>/<capture_id>.json
```

`capture_id` is `<UTC time as YYYYMMDDTHHMMSSmmmZ>_<sequence>`, for example `20261121T154210123Z_000412`. The sequence counter increases on every capture and never resets except when the SD card is wiped, so captures sort correctly even if the clock is wrong.

## Photo

- JPEG, full sensor resolution from the Camera Module 3 (4608 × 2592), quality 90 or higher.
- No resizing, cropping or filters on the Pi. The cloud needs the original.
- Keep the EXIF the camera writes (exposure, gain, focal length).

## JSON metadata

```json
{
  "format_version": "0.1-draft",
  "capture_id": "20261121T154210123Z_000412",
  "device_id": "pivotcam-01",
  "field_id": "field-A",

  "time": {
    "utc": "2026-11-21T15:42:10.123Z",
    "source": "gps",
    "monotonic_ms": 31415926
  },

  "pivot": {
    "angle_deg": 137.4,
    "angle_source": "imu",
    "camera_radius_m": 182.0,
    "pass_id": "2026-11-21_pass01"
  },

  "camera": {
    "tilt_deg": 35.0,
    "tilt_source": "imu",
    "roll_deg": 0.8,
    "heading_deg": 227.4,
    "height_m": 3.8,
    "model": "camera-module-3",
    "lens": "standard",
    "resolution": [4608, 2592],
    "exposure_us": 2000,
    "analog_gain": 1.0,
    "focus": "auto"
  },

  "gps": {
    "lat": 38.5449,
    "lon": -121.7405,
    "alt_m": 18.2,
    "fix": "3d",
    "hdop": 0.9,
    "source": "pi-gps-hat"
  },

  "pivot_center": {
    "lat": 38.5461,
    "lon": -121.7390,
    "source": "configured"
  },

  "upload": {
    "attempt": 1
  }
}
```

## Field rules

| Field | Required | Notes |
|---|---|---|
| `format_version`, `capture_id`, `device_id`, `field_id` | Yes | |
| `time.utc` | Yes | ISO 8601 UTC with milliseconds. |
| `time.source` | Yes | `gps`, `ntp` or `rtc`. If the clock was never synced, use `unsynced`; the cloud then orders by `capture_id` sequence. |
| `time.monotonic_ms` | Yes | Milliseconds since boot. Lets the cloud space photos even when the wall clock jumps. |
| `pivot.angle_deg` | Yes, or `null` | Arm angle from north, clockwise, 0–360. `null` if not measured. |
| `pivot.angle_source` | Yes | `imu`, `encoder`, `gps` (computed from GPS and `pivot_center`) or `none`. |
| `pivot.camera_radius_m` | Yes | Distance from pivot center to the camera along the arm. Set at install. |
| `pivot.pass_id` | Optional | Groups photos from one sweep of the arm. |
| `camera.tilt_deg` | Yes | Degrees down from horizontal. From the IMU if there is one, otherwise the installed value with `tilt_source: "installed"`. |
| `camera.roll_deg`, `heading_deg` | Optional | `null` if no IMU. |
| `camera.height_m` | Yes | Camera height above ground, set at install. |
| `camera.resolution` | Yes | `[width, height]` of the saved JPEG. |
| `camera.exposure_us`, `analog_gain`, `focus` | Optional | Helps the cloud reject blurred or dark frames. |
| `gps` | Optional | The whole object is `null` if there's no GPS. Never fill it with the pivot center or a guess. |
| `pivot_center` | Yes | Set once at install. `source` is `configured` or `surveyed`. |
| `upload.attempt` | Optional | Retry count, for debugging flaky links. |

Unknown or unmeasured values are `null`, never a made-up default. Extra fields are allowed; the cloud ignores what it doesn't know.

## Upload

To be decided with Tushar. Proposal: the Pi writes to the SD card first, then uploads the `.jpg` and `.json` pair to cloud storage when it has a connection. The JSON is uploaded **after** the photo, so a JSON in storage always means its photo is complete. Nothing is deleted from the SD card until the cloud confirms both files.

## Relation to the older contract

[shared/capture-contract.md](../shared/capture-contract.md) describes the hackathon ESP32 camera posting to the local dashboard backend. This file replaces it for the Pi. The backend endpoint will be updated once this format is agreed.

## Open questions for Tushar

1. Which sensor gives the pivot angle: an IMU on the mount, a GPS module, or the pivot controller?
2. Is there a GPS module on the Pi, and which one?
3. Capture trigger: every N seconds, or every N degrees of arm travel?
4. What connection is at the field (Wi-Fi from the farm, LTE, or upload when the Pi comes back)?
5. Is the tilt fixed, or will the "6-axis gimbal" move it? If it moves, tilt must come from the IMU on every frame.
