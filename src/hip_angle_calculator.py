import csv
import math


INPUT_PATH = "data/pose_data/test_pitch_pose_named.csv"
OUTPUT_PATH = "data/pose_data/test_pitch_hip_angles.csv"


def calculate_hip_angle(left_hip, right_hip):
    """
    計算左右髖部連線相對於水平線的角度。
    """

    dx = right_hip[0] - left_hip[0]
    dy = right_hip[1] - left_hip[1]

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
        "hip_angle"
    ])

    for frame in sorted(landmarks_by_frame):

        landmarks = landmarks_by_frame[frame]

        hip_angle = None

        if all(
            name in landmarks
            for name in [
                "LEFT_HIP",
                "RIGHT_HIP"
            ]
        ):
            hip_angle = calculate_hip_angle(
                landmarks["LEFT_HIP"],
                landmarks["RIGHT_HIP"]
            )

        writer.writerow([
            frame,
            hip_angle
        ])


print("髖部角度計算完成")
print(f"輸出檔案：{OUTPUT_PATH}")