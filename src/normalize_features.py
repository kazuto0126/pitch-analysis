import csv


INPUT_PATH = "data/pose_data/test_pitch_features.csv"
OUTPUT_PATH = "data/pose_data/test_pitch_features_normalized.csv"


FEATURE_COLUMNS = [
    "left_knee_angle",
    "right_knee_angle",
    "shoulder_angle",
    "left_elbow_angle",
    "right_elbow_angle",
    "hip_angle",
    "stride_distance",
]


def min_max_normalize(values):
    """
    將數值轉換到 0～1。
    """

    minimum = min(values)
    maximum = max(values)

    if maximum == minimum:
        return [0.0 for _ in values]

    return [
        (value - minimum) / (maximum - minimum)
        for value in values
    ]


# 讀取資料
rows = []

with open(INPUT_PATH, "r", encoding="utf-8-sig") as file:

    reader = csv.DictReader(file)

    for row in reader:
        rows.append(row)


# 對每一個特徵分別進行標準化
for column in FEATURE_COLUMNS:

    values = []

    for row in rows:

        if row[column] != "":
            values.append(float(row[column]))

    normalized_values = min_max_normalize(values)

    index = 0

    for row in rows:

        if row[column] != "":

            row[column] = normalized_values[index]
            index += 1


# 寫入新的 CSV
with open(
    OUTPUT_PATH,
    "w",
    newline="",
    encoding="utf-8-sig"
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=[
            "frame",
            *FEATURE_COLUMNS
        ]
    )

    writer.writeheader()

    writer.writerows(rows)


print("特徵標準化完成")
print(f"輸出檔案：{OUTPUT_PATH}")