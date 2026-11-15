"""Train crop identity from all class folders in Fruits-360 100x100.

Dataset: https://github.com/fruits-360/fruits-360-100x100
Supply its extracted root with Training and Test. Optional Validation must
contain the same classes. Keep the test set separate during training.
Use a separate real-camera split to measure performance on plants in the field.
Usage: python train_crop_classifier.py FRUITS360_ROOT --output GroundZero_Trained
"""

from train_plant_detector import train


if __name__ == "__main__":
    train("crop_model", "Crop", "Train all supplied Fruits-360 crop classes.")
