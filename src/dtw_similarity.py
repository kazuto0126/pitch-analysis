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


def frame_distance(vector_a, vector_b):

    total = 0.0

    for a, b in zip(vector_a, vector_b):

        total += (a - b) ** 2

    return math.sqrt(total)


def dtw_distance(sequence_a, sequence_b):

    n = len(sequence_a)
    m = len(sequence_b)

    dp = [
        [float("inf")] * (m + 1)
        for _ in range(n + 1)
    ]

    dp[0][0] = 0.0

    for i in range(1, n + 1):

        for j in range(1, m + 1):

            cost = frame_distance(
                sequence_a[i - 1],
                sequence_b[j - 1]
            )

            dp[i][j] = cost + min(
                dp[i - 1][j],
                dp[i][j - 1],
                dp[i - 1][j - 1]
            )

    return dp[n][m]


features = load_features(INPUT_PATH)


# 測試：把同一個投球動作分成兩段
middle = len(features) // 2

sequence_a = features[:middle]
sequence_b = features[middle:]


distance = dtw_distance(
    sequence_a,
    sequence_b
)


print("DTW 相似度測試")
print("=" * 50)

print(f"完整影格數：{len(features)}")
print(f"第一段影格數：{len(sequence_a)}")
print(f"第二段影格數：{len(sequence_b)}")

print(f"\nDTW 距離：{distance:.6f}")