import csv


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


with open(INPUT_PATH, "r", encoding="utf-8-sig") as file:

    reader = csv.DictReader(file)

    rows = list(reader)


print("標準化資料檢查")
print("=" * 50)

print(f"總影格數：{len(rows)}")


for column in FEATURE_COLUMNS:

    values = []

    for row in rows:

        if row[column] != "":
            values.append(float(row[column]))

    minimum = min(values)
    maximum = max(values)

    print(
        f"{column:20s} "
        f"最小值 = {minimum:.4f}, "
        f"最大值 = {maximum:.4f}"
    )


print("\n前 5 筆標準化資料")
print("=" * 50)

for row in rows[:5]:

    print(row)