# Capture contract (camera → backend)

Agreed with the hardware teammate's `FieldOS_Camera_Data.xlsx`. If anything here changes, update the firmware and this file together.

`POST http://<LAPTOP_LAN_IP>:8000/api/captures` — returns `201` with `{"capture_id","stored":true,"zone_id","image_url"}`.

| Field | Where | Availability | Example | Handling |
|---|---|---|---|---|
| Raw JPEG | Body | Required | 320 × 240 JPEG | Original camera image as binary JPEG bytes (not base64, not multipart). Max 2 MB. |
| Content-Type | Header | Required | `image/jpeg` | Raw body with this media type. |
| X-Device-ID | Header | Required | `fieldos-esp32-01` | Identifies the camera. |
| X-Field-ID | Header | Required | `field-A` | Configured field identifier. |
| X-Zone-ID | Header | Required | `demo-zone-1` | Manually assigned zone. `demo-zone-1` maps to zone `F6`; `A1`..`L12` are used as-is. |
| X-Edge-Label | Header | Required | `discoloration` | `healthy`, `discoloration` or `wilting`. Visible leaf appearance only. Other values are stored and flagged. |
| X-Edge-Confidence | Header | Required | `0.7200` | Model score 0–1 for the reported label (clamped). |
| X-Capture-Uptime-Ms | Header | Required | `31415` | Milliseconds since device boot at capture. |
| X-Timestamp-Unix | Header | Optional | `1794700000` | Unix seconds, only when the device clock is synced. Otherwise `captured_at` is `null`. |
| X-Inference-Ms | Header | Optional | `1840` | Condition model inference time. |
| X-Model-Version | Header | Optional | `cropvision-tiny-v1` | Version of the condition model. |
| Image width, height, size | Backend | Derived | 320 × 240 px | Read from the JPEG. |
| received_at | Backend | Generated | Server timestamp | When the backend received the capture. |
| Plant check and score | ESP32 only | Local | plant / no_plant | Only passing frames are uploaded. The score stays on the device. |
| GPS and sensor readings | Separate sources | Outside contract | — | Stored as `null` until a telemetry source exists. Never invented. |
| Brightness, blur, greenness | Fallback only | Pending agreement | — | Not accepted until a fallback payload is agreed. |

Errors: missing required header → `400 {"error":"missing_header","header":"X-..."}`; not a JPEG → `415`; body over 2 MB → `413`.

Test without the board:

```bash
curl -X POST http://localhost:8000/api/captures -H "Content-Type: image/jpeg" -H "X-Device-ID: fieldos-esp32-01" -H "X-Field-ID: field-A" -H "X-Zone-ID: demo-zone-1" -H "X-Edge-Label: discoloration" -H "X-Edge-Confidence: 0.72" -H "X-Capture-Uptime-Ms: 31415" --data-binary @frontend/public/demo/images/discoloration_01.jpg
```
