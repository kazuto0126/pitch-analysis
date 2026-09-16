import csv
import math


INPUT_PATH = "data/pose_data/test_pitch_pose_named.csv"
OUTPUT_PATH = "data/pose_data/test_pitch_shoulder_angles.csv"


def calculate_shoulder_angle(left_shoulder, right_shoulder):
    """
    計算左右肩膀連線相對於水平線的角度。
    """

    dx = right_shoulder[0] - left_shoulder[0]
    dy = right_shoulder[1] - left_shoulder[1]

    if dx == 0 and dy == 0:
        return None

    angle = math.degrees(math.atan2(dy, dx))

    return angle


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
        "shoulder_angle"
    ])

    for frame in sorted(landmarks_by_frame):

        landmarks = landmarks_by_frame[frame]

        shoulder_angle = None

        if all(
            name in landmarks
            for name in [
                "LEFT_SHOULDER",
                "RIGHT_SHOULDER"
            ]
        ):
            shoulder_angle = calculate_shoulder_angle(
                landmarks["LEFT_SHOULDER"],
                landmarks["RIGHT_SHOULDER"]
            )

        writer.writerow([
            frame,
            shoulder_angle
        ])


print("肩膀角度計算完成")
print(f"輸出檔案：{OUTPUT_PATH}")