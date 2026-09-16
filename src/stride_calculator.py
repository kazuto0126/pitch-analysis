import csv


INPUT_PATH = "data/pose_data/test_pitch_pose_named.csv"
OUTPUT_PATH = "data/pose_data/test_pitch_stride.csv"


landmarks_by_frame = {}


with open(INPUT_PATH, "r", encoding="utf-8-sig") as file:

    reader = csv.DictReader(file)

    for row in reader:

        frame = int(row["frame"])
        landmark = row["landmark"]

        x = float(row["x"])
        y = float(row["y"])

        if frame not in landmarks_by_frame:
            landmarks_by_frame[frame] = {}

        landmarks_by_frame[frame][landmark] = (x, y)


with open(
    OUTPUT_PATH,
    "w",
    newline="",
    encoding="utf-8-sig"
) as file:

    writer = csv.writer(file)

    writer.writerow([
        "frame",
        "stride_distance"
    ])

    for frame in sorted(landmarks_by_frame):

        landmarks = landmarks_by_frame[frame]

        stride_distance = None

        if all(
            name in landmarks
            for name in [
                "LEFT_ANKLE",
                "RIGHT_ANKLE"
            ]
        ):

            left_ankle = landmarks["LEFT_ANKLE"]
            right_ankle = landmarks["RIGHT_ANKLE"]

            # 使用影像座標計算兩腳的水平距離
            stride_distance = abs(
                left_ankle[0] - right_ankle[0]
            )

        writer.writerow([
            frame,
            stride_distance
        ])


print("步幅計算完成")
print(f"輸出檔案：{OUTPUT_PATH}")