"""Train the plant presence gate and provide the shared INT8 export pipeline.

Install tensorflow, numpy and pillow in a Python 3.11 or 3.12 environment.
Usage: python train_plant_detector.py DATASET --output GroundZero_Trained
Dataset: Training/{no_plant,plant}, Test/{no_plant,plant}, optional Validation.
Include picked fruit and foliage as plant examples and empty scenes, hands and
colored non-plants as negatives. Split by specimen and recording session.
"""

import argparse
import hashlib
import json
from pathlib import Path

SIZE = 96
SEED = 42
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}


def classes_in(folder):
    return sorted(
        p.name for p in folder.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )


def train(stem, symbol, description, required=(), exact=False):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent)
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--max-per-class", type=int, default=0,
                        help="Optional per-class cap in Training only")
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.max_per_class < 0:
        parser.error("epochs and batch-size must be positive and the cap nonnegative")

    import numpy as np
    import tensorflow as tf
    from PIL import Image

    tf.keras.utils.set_random_seed(SEED)
    root = args.dataset
    names = classes_in(root / "Training")
    if len(names) < 2 or not set(required).issubset(names):
        parser.error(f"Training must contain at least two classes, including {required}")
    if exact and set(names) != set(required):
        parser.error(f"Training must contain exactly {required}")
    if any(any(char in name for char in ',\r\n"') for name in names):
        parser.error('Class names must exclude commas, quotes and line breaks')

    rng = np.random.default_rng(SEED)

    def split_rows(folder, cap=0):
        if classes_in(folder) != names:
            parser.error(f"{folder} must contain the same classes as Training")
        buckets = []
        for name in names:
            images = sorted(
                p for p in (folder / name).rglob("*")
                if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
            )
            if not images:
                parser.error(f"No images in {folder / name}")
            order = rng.permutation(len(images))
            buckets.append([str(images[i]) for i in (order[:cap] if cap else order)])
        return buckets

    training = split_rows(root / "Training", args.max_per_class)
    testing = split_rows(root / "Test")
    if (root / "Validation").is_dir():
        validation = split_rows(root / "Validation")
        validation_source = "provided Validation split"
    else:
        if min(map(len, training)) < 2:
            parser.error("Need at least two Training images per class to make a validation split")
        cutoffs = [max(1, len(bucket) // 10) for bucket in training]
        validation = [bucket[:n] for bucket, n in zip(training, cutoffs)]
        training = [bucket[n:] for bucket, n in zip(training, cutoffs)]
        validation_source = "image-level split of Training; related images may overlap"

    def load_image(item):
        with Image.open(item.numpy().decode()) as source:
            pixels = np.asarray(source.convert("RGB"))
        height, width = pixels.shape[:2]
        side = min(height, width)
        top, left = (height - side) // 2, (width - side) // 2
        indices = np.arange(SIZE) * side // SIZE
        return pixels[top + indices[:, None], left + indices].astype(np.float32) / 255.0

    def decode(path, label):
        pixels = tf.py_function(load_image, [path], Tout=tf.float32)
        pixels.set_shape((SIZE, SIZE, 3))
        return pixels, label

    def dataset(buckets, shuffle=False):
        paths = [path for bucket in buckets for path in bucket]
        targets = [i for i, bucket in enumerate(buckets) for _ in bucket]
        data = tf.data.Dataset.from_tensor_slices((paths, targets))
        if shuffle:
            data = data.shuffle(min(len(paths), 4096), seed=SEED)
        return data.map(decode, num_parallel_calls=tf.data.AUTOTUNE).batch(
            args.batch_size
        ).prefetch(tf.data.AUTOTUNE)

    train_data = dataset(training, shuffle=True)
    val_data = dataset(validation)
    test_data = dataset(testing)
    model = tf.keras.Sequential([
        tf.keras.Input(shape=(SIZE, SIZE, 3)),
        tf.keras.layers.RandomFlip("horizontal"),
        tf.keras.layers.Conv2D(12, 3, strides=2, padding="same", activation="relu"),
        tf.keras.layers.SeparableConv2D(24, 3, strides=2, padding="same", activation="relu"),
        tf.keras.layers.SeparableConv2D(40, 3, strides=2, padding="same", activation="relu"),
        tf.keras.layers.SeparableConv2D(64, 3, strides=2, padding="same", activation="relu"),
        tf.keras.layers.GlobalAveragePooling2D(),
        tf.keras.layers.Dense(len(names), activation="softmax"),
    ])
    model.compile(optimizer="adam", loss="sparse_categorical_crossentropy",
                  metrics=["accuracy"])
    model.fit(train_data, validation_data=val_data, epochs=args.epochs, callbacks=[
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=5, restore_best_weights=True
        )
    ])
    float_metrics = model.evaluate(test_data, return_dict=True)

    def representative_images():
        for images, _ in train_data.unbatch().take(256):
            yield [images.numpy()[None, ...]]

    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = representative_images
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8
    tflite = converter.convert()

    interpreter = tf.lite.Interpreter(model_content=tflite)
    interpreter.allocate_tensors()
    inp = interpreter.get_input_details()[0]
    out = interpreter.get_output_details()[0]
    scale, zero_point = inp["quantization"]
    confusion = np.zeros((len(names), len(names)), dtype=np.int64)
    for image, label in test_data.unbatch().as_numpy_iterator():
        quantized = np.clip(np.rint(image / scale) + zero_point, -128, 127)
        interpreter.set_tensor(inp["index"], quantized[None].astype(np.int8))
        interpreter.invoke()
        prediction = int(interpreter.get_tensor(out["index"])[0].argmax())
        confusion[int(label), prediction] += 1

    model_id = hashlib.sha256(tflite).hexdigest()[:12]
    metrics = {
        "model_id": model_id,
        "dataset_path": str(root),
        "classes_in_output_order": names,
        "training_counts": dict(zip(names, map(len, training))),
        "validation_counts": dict(zip(names, map(len, validation))),
        "test_counts": dict(zip(names, map(len, testing))),
        "validation_source": validation_source,
        "test_float_accuracy": float(float_metrics["accuracy"]),
        "test_int8_accuracy": float(confusion.trace() / confusion.sum()),
        "test_int8_recall_by_class": dict(zip(
            names, (confusion.diagonal() / confusion.sum(axis=1)).tolist()
        )),
        "test_int8_confusion_matrix_true_rows": confusion.tolist(),
        "tflite_bytes": len(tflite),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / f"{stem}.tflite").write_bytes(tflite)
    (args.output / f"{stem}_metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "  " + ", ".join(f"0x{byte:02x}" for byte in tflite[i:i + 16]) + ","
        for i in range(0, len(tflite), 16)
    ]
    labels = ", ".join(json.dumps(name, ensure_ascii=False) for name in names)
    header = (
        "#pragma once\n"
        f"alignas(16) static const unsigned char k{symbol}Model[] = {{\n"
        + "\n".join(lines)
        + f"\n}};\nstatic const char* const k{symbol}Labels[] = {{{labels}}};\n"
        + f"static constexpr char k{symbol}ModelId[] = \"{model_id}\";\n"
    )
    (args.output / f"{stem}.h").write_text(header, encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    train("plant_model", "Plant", "Train the plant-presence detector.",
          required=("no_plant", "plant"), exact=True)
