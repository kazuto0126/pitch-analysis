import csv
import math


INPUT_PATH = "data/pose_data/test_pitch_features_normalized.csv"


FEATURE_COLUMNS = [
    "left_knee_angle",
    "right_knee_angle",
    "shoulder_angle",
    "left_elbow_angle",
    "right_elbow_angle",
    "hip_angle",
    "stride_distance",
]


def load_features(path):

    data = []

    with open(path, "r", encoding="utf-8-sig") as file:

        reader = csv.DictReader(file)

        for row in reader:

            features = []

            for column in FEATURE_COLUMNS:

                if row[column] == "":
                    features.append(0.0)
                else:
                    features.append(float(row[column]))

            data.append(features)

    return data


def euclidean_distance(vector_a, vector_b):

    total = 0.0

    for a, b in zip(vector_a, vector_b):

        total += (a - b) ** 2

    return math.sqrt(total)


features = load_features(INPUT_PATH)


print("相似度測試")
print("=" * 50)

print(f"有效影格數：{len(features)}")
print(f"特徵數量：{len(FEATURE_COLUMNS)}")


# 比較第 0 幀與第 1 幀
distance_01 = euclidean_distance(
    features[0],
    features[1]
)


# 比較第 0 幀與第 100 幀
distance_0100 = euclidean_distance(
    features[0],
    features[100]
)


print("\n距離測試：")

print(
    f"Frame 0 ↔ Frame 1："
    f"{distance_01:.6f}"
)

print(
    f"Frame 0 ↔ Frame 100："
    f"{distance_0100:.6f}"
)