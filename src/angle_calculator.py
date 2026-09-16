import csv
import math


INPUT_PATH = "data/pose_data/test_pitch_pose_named.csv"
OUTPUT_PATH = "data/pose_data/test_pitch_angles.csv"


def calculate_angle(point_a, point_b, point_c):
    """
    計算 A-B-C 的夾角。
    B 是角度的頂點。
    """

    vector_ba = (
        point_a[0] - point_b[0],
        point_a[1] - point_b[1],
    )

    vector_bc = (
        point_c[0] - point_b[0],
        point_c[1] - point_b[1],
    )

    dot_product = (
        vector_ba[0] * vector_bc[0]
        + vector_ba[1] * vector_bc[1]
    )

    length_ba = math.sqrt(
        vector_ba[0] ** 2
        + vector_ba[1] ** 2
    )

    length_bc = math.sqrt(
        vector_bc[0] ** 2
        + vector_bc[1] ** 2
    )

    if length_ba == 0 or length_bc == 0:
        return None

    cos_angle = dot_product / (length_ba * length_bc)

    cos_angle = max(-1.0, min(1.0, cos_angle))

    angle = math.degrees(math.acos(cos_angle))

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
        "left_knee_angle",
        "right_knee_angle"
    ])

    for frame in sorted(landmarks_by_frame):

        landmarks = landmarks_by_frame[frame]

        left_angle = None
        right_angle = None

        if all(
            name in landmarks
            for name in [
                "LEFT_HIP",
                "LEFT_KNEE",
                "LEFT_ANKLE"
            ]
        ):
            left_angle = calculate_angle(
                landmarks["LEFT_HIP"],
                landmarks["LEFT_KNEE"],
                landmarks["LEFT_ANKLE"]
            )

        if all(
            name in landmarks
            for name in [
                "RIGHT_HIP",
                "RIGHT_KNEE",
                "RIGHT_ANKLE"
            ]
        ):
            right_angle = calculate_angle(
                landmarks["RIGHT_HIP"],
                landmarks["RIGHT_KNEE"],
                landmarks["RIGHT_ANKLE"]
            )

        writer.writerow([
            frame,
            left_angle,
            right_angle
        ])


print("膝蓋角度計算完成")
print(f"輸出檔案：{OUTPUT_PATH}")