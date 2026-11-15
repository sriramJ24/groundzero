"""Train visible soil-surface classification from labeled photos.

Dataset candidate: https://github.com/Phantom-fs/Soil-Classification-Dataset
Organize the source classes into Training and Test, optionally Validation.
Split images by site or source to avoid near duplicates across splits.
Add soil_not_visible to each split using plant photos with no exposed soil.
Run on plant scenes only. Use a separate field test with soil visible in frame.
Usage: python train_soil_classifier.py SOIL_ROOT --output GroundZero_Trained
"""

from train_plant_detector import train


if __name__ == "__main__":
    train("soil_model", "Soil", "Train visible soil-surface classes.",
          required=("soil_not_visible",))
