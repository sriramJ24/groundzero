#include <Arduino.h>
#include <SD_MMC.h>
#include <esp_camera.h>
#include <esp_heap_caps.h>
#include <esp_system.h>
#include <img_converters.h>
#include <time.h>
#include <Chirale_TensorFlowLite.h>
#include "tensorflow/lite/micro/all_ops_resolver.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/schema/schema_generated.h"
#include "plant_model.h"
#include "crop_model.h"
#include "soil_model.h"

// AI Thinker ESP32-CAM, Huge APP partition, Chirale_TensorFlowLite 2.0.0.
// Generate the three headers with the Python trainers before compiling.
// The SD card stores one capture CSV per boot and one JPEG per captured frame.
constexpr int kWidth = 320, kHeight = 240, kInput = 96;
constexpr uint32_t kIntervalMs = 5000;
constexpr size_t kArenaBytes = 256 * 1024;
constexpr float kPlantThreshold = 0.80f;
constexpr float kCropThreshold = 0.55f;
constexpr float kSoilThreshold = 0.65f;
constexpr size_t kCropCount = sizeof(kCropLabels) / sizeof(kCropLabels[0]);
constexpr size_t kSoilCount = sizeof(kSoilLabels) / sizeof(kSoilLabels[0]);
constexpr char kDevice[] = "groundzero-esp32-01";
constexpr char kField[] = "field-A";
constexpr char kZone[] = "demo-zone-1";
constexpr char kCsvHeader[] =
    "capture_id,capture_number,capture_time_utc,capture_uptime_ms,"
    "received_at_utc,device_id,field_id,zone_id,plant_status,crop_label,"
    "crop_confidence,condition_label,condition_confidence,inference_ms,"
    "model_version,content_type,jpeg_width,jpeg_height,jpeg_bytes,"
    "jpeg_filename,analysis_method,method_version,processing_ms,"
    "plant_confidence,soil_surface,soil_confidence";

tflite::AllOpsResolver resolver;
tflite::MicroInterpreter* plant = nullptr;
tflite::MicroInterpreter* crop = nullptr;
tflite::MicroInterpreter* soil = nullptr;
uint8_t* decoded = nullptr;
bool cameraReady = false, sdReady = false;
uint32_t lastCaptureMs = 0;
unsigned long captureNumber = 0;
char session[9];
char csvPath[40];

bool initCamera() {
  camera_config_t config = {};
  config.pin_pwdn = 32;
  config.pin_reset = -1;
  config.pin_xclk = 0;
  config.pin_sccb_sda = 26;
  config.pin_sccb_scl = 27;
  config.pin_d7 = 35;
  config.pin_d6 = 34;
  config.pin_d5 = 39;
  config.pin_d4 = 36;
  config.pin_d3 = 21;
  config.pin_d2 = 19;
  config.pin_d1 = 18;
  config.pin_d0 = 5;
  config.pin_vsync = 25;
  config.pin_href = 23;
  config.pin_pclk = 22;
  config.xclk_freq_hz = 20000000;
  config.ledc_timer = LEDC_TIMER_0;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_QVGA;
  config.jpeg_quality = 12;
  config.fb_count = 1;
  config.fb_location = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;

  const esp_err_t status = esp_camera_init(&config);
  if (status != ESP_OK) Serial.printf("Camera init failed: 0x%x\n", status);
  return status == ESP_OK;
}

tflite::MicroInterpreter* initModel(const unsigned char* bytes, int classes,
                                   const char* name) {
  const auto* model = tflite::GetModel(bytes);
  if (model->version() != TFLITE_SCHEMA_VERSION) {
    Serial.printf("%s: incompatible model schema\n", name);
    return nullptr;
  }
  auto* arena = static_cast<uint8_t*>(
      heap_caps_malloc(kArenaBytes, MALLOC_CAP_SPIRAM));
  if (!arena) {
    Serial.printf("%s: could not allocate tensor arena\n", name);
    return nullptr;
  }
  auto* runner = new tflite::MicroInterpreter(model, resolver, arena, kArenaBytes);
  if (runner->AllocateTensors() == kTfLiteOk) {
    const auto* in = runner->input(0);
    const auto* out = runner->output(0);
    if (in && out && in->type == kTfLiteInt8 && out->type == kTfLiteInt8 &&
        in->dims->size == 4 && in->dims->data[0] == 1 &&
        in->dims->data[1] == kInput && in->dims->data[2] == kInput &&
        in->dims->data[3] == 3 && out->dims->size == 2 &&
        out->dims->data[0] == 1 && out->dims->data[1] == classes &&
        in->params.scale > 0 && out->params.scale > 0) {
      Serial.printf("%s arena used: %u bytes\n", name,
                    static_cast<unsigned>(runner->arena_used_bytes()));
      return runner;
    }
  }
  Serial.printf("%s: invalid tensors or arena allocation failed\n", name);
  delete runner;
  heap_caps_free(arena);
  return nullptr;
}

bool infer(tflite::MicroInterpreter* runner, const char* const* labels,
           size_t count, float threshold, const char*& label, char* scoreText,
           int requestedIndex) {
  label = "unavailable";
  if (!runner) return false;
  auto* input = runner->input(0);
  int8_t quantized[256];
  for (int i = 0; i < 256; ++i) {
    const long value = lrintf((i / 255.0f) / input->params.scale) +
                       input->params.zero_point;
    quantized[i] = static_cast<int8_t>(constrain(value, -128L, 127L));
  }
  auto* target = input->data.int8;
  for (int y = 0; y < kInput; ++y) {
    for (int x = 0; x < kInput; ++x) {
      const int sourceX = (kWidth - kHeight) / 2 + x * kHeight / kInput;
      const int sourceY = y * kHeight / kInput;
      const auto* bgr = decoded + 3 * (sourceY * kWidth + sourceX);
      *target++ = quantized[bgr[2]];
      *target++ = quantized[bgr[1]];
      *target++ = quantized[bgr[0]];
    }
  }
  if (runner->Invoke() != kTfLiteOk) return false;
  const auto* out = runner->output(0);
  int best = requestedIndex;
  if (best < 0) {
    best = 0;
    for (size_t i = 1; i < count; ++i) {
      if (out->data.int8[i] > out->data.int8[best]) best = i;
    }
  }
  const float score = (out->data.int8[best] - out->params.zero_point) *
                      out->params.scale;
  if (!isfinite(score) || score < -0.01f || score > 1.01f) return false;
  snprintf(scoreText, 16, "%.4f", constrain(score, 0.0f, 1.0f));
  label = score >= threshold ? labels[best] : "unknown";
  return true;
}

void setup() {
  Serial.begin(115200);
  if (!psramFound()) {
    Serial.println("PSRAM is required for image decoding and inference.");
    return;
  }
  decoded = static_cast<uint8_t*>(
      heap_caps_malloc(kWidth * kHeight * 3, MALLOC_CAP_SPIRAM));
  if (!decoded || !initCamera()) return;

  static_assert(sizeof(kPlantLabels) / sizeof(kPlantLabels[0]) == 2,
                "Plant detector must have two classes");
  if (strcmp(kPlantLabels[0], "no_plant") != 0 ||
      strcmp(kPlantLabels[1], "plant") != 0) {
    Serial.println("Plant detector label order must be no_plant, plant.");
    return;
  }
  plant = initModel(kPlantModel, 2, "Plant");
  crop = initModel(kCropModel, kCropCount, "Crop");
  soil = initModel(kSoilModel, kSoilCount, "Soil");

  snprintf(session, sizeof(session), "%08lx",
           static_cast<unsigned long>(esp_random()));
  snprintf(csvPath, sizeof(csvPath), "/captures_%s.csv", session);
  if (SD_MMC.begin("/sdcard", true)) {
    File csv = SD_MMC.open(csvPath, FILE_WRITE);
    if (csv) {
      sdReady = csv.println(kCsvHeader) == strlen(kCsvHeader) + 2;
      csv.close();
    }
  }
  if (sdReady) Serial.printf("Recording on microSD: %s\n", csvPath);
  else Serial.println("microSD unavailable. Recording CSV rows over USB.");
  Serial.printf("CSV_HEADER,%s\n", kCsvHeader);
  lastCaptureMs = millis() - kIntervalMs;
  cameraReady = true;
}

void loop() {
  if (!cameraReady || millis() - lastCaptureMs < kIntervalMs) {
    delay(20);
    return;
  }
  lastCaptureMs = millis();
  camera_fb_t* frame = esp_camera_fb_get();
  if (!frame) {
    Serial.println("Camera capture failed.");
    return;
  }

  ++captureNumber;
  const uint32_t capturedMs = millis();
  const time_t capturedAt = time(nullptr);
  const char* status = "Plant check failed";
  const char* cropLabel = "";
  const char* soilLabel = "";
  char plantScore[16] = "", cropScore[16] = "", soilScore[16] = "";
  char inferenceMs[16] = "";
  const char* gate = nullptr;

  if (frame->width == kWidth && frame->height == kHeight &&
      frame->format == PIXFORMAT_JPEG &&
      fmt2rgb888(frame->buf, frame->len, frame->format, decoded)) {
    const uint32_t inferenceStarted = millis();
    if (infer(plant, kPlantLabels, 2, kPlantThreshold, gate, plantScore, 1)) {
      if (strcmp(gate, "plant") == 0) {
        status = "Plant detected";
        infer(crop, kCropLabels, kCropCount, kCropThreshold, cropLabel, cropScore, -1);
        infer(soil, kSoilLabels, kSoilCount, kSoilThreshold, soilLabel, soilScore, -1);
      } else {
        status = "Plant not found";
      }
      snprintf(inferenceMs, sizeof(inferenceMs), "%lu",
               static_cast<unsigned long>(millis() - inferenceStarted));
    }
  }
  const uint32_t processingMs = millis() - capturedMs;
  Serial.printf("Capture %lu: %s.", captureNumber, status);
  if (cropLabel[0]) {
    Serial.printf(" Crop: %s. Soil surface: %s.", cropLabel, soilLabel);
  }
  Serial.println();

  char jpegName[40] = "";
  if (sdReady) {
    char imagePath[42];
    snprintf(imagePath, sizeof(imagePath), "/%s_%06lu.jpg", session, captureNumber);
    File image = SD_MMC.open(imagePath, FILE_WRITE);
    if (image) {
      const size_t written = image.write(frame->buf, frame->len);
      image.close();
      if (written == frame->len) {
        snprintf(jpegName, sizeof(jpegName), "%s", imagePath + 1);
      } else {
        SD_MMC.remove(imagePath);
      }
    }
    if (!jpegName[0]) Serial.println("JPEG save failed.");
  }

  const unsigned width = frame->width, height = frame->height, bytes = frame->len;
  esp_camera_fb_return(frame);
  char timestamp[25] = "";
  struct tm utc;
  if (capturedAt >= 1767225600 && gmtime_r(&capturedAt, &utc)) {
    strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", &utc);
  }

  // Write the CSV record last, after inference and the JPEG save attempt.
  char row[768];
  const int length = snprintf(
      row, sizeof(row),
      "%s-%lu,%lu,%s,%lu,,%s,%s,%s,%s,%s,%s,,,%s,%s/%s/%s,"
      "image/jpeg,%u,%u,%u,%s,tinyml_int8,groundzero-trained-v1,%lu,%s,%s,%s",
      session, captureNumber, captureNumber, timestamp,
      static_cast<unsigned long>(capturedMs), kDevice, kField, kZone,
      status, cropLabel, cropScore, inferenceMs,
      kPlantModelId, kCropModelId, kSoilModelId,
      width, height, bytes, jpegName,
      static_cast<unsigned long>(processingMs), plantScore, soilLabel, soilScore);
  if (length < 0 || length >= static_cast<int>(sizeof(row))) {
    Serial.println("CSV row too long.");
    return;
  }
  if (sdReady) {
    File csv = SD_MMC.open(csvPath, FILE_APPEND);
    if (csv) {
      const size_t written = csv.println(row);
      csv.close();
      if (written == static_cast<size_t>(length) + 2) return;
    }
    Serial.println("microSD CSV append failed. Row follows over USB.");
  }
  Serial.printf("CSV,%s\n", row);
}
