import csv
import matplotlib.pyplot as plt


INPUT_PATH = "data/pose_data/test_pitch_features.csv"
OUTPUT_PATH = "data/pose_data/all_features.png"


frames = []

left_knee = []
right_knee = []

shoulder = []

left_elbow = []
right_elbow = []

hip = []

stride = []


with open(INPUT_PATH, "r", encoding="utf-8-sig") as file:

    reader = csv.DictReader(file)

    for row in reader:

        frames.append(int(row["frame"]))

        left_knee.append(
            float(row["left_knee_angle"])
            if row["left_knee_angle"]
            else None
        )

        right_knee.append(
            float(row["right_knee_angle"])
            if row["right_knee_angle"]
            else None
        )

        shoulder.append(
            float(row["shoulder_angle"])
            if row["shoulder_angle"]
            else None
        )

        left_elbow.append(
            float(row["left_elbow_angle"])
            if row["left_elbow_angle"]
            else None
        )

        right_elbow.append(
            float(row["right_elbow_angle"])
            if row["right_elbow_angle"]
            else None
        )

        hip.append(
            float(row["hip_angle"])
            if row["hip_angle"]
            else None
        )

        stride.append(
            float(row["stride_distance"])
            if row["stride_distance"]
            else None
        )


fig, axes = plt.subplots(
    4,
    1,
    figsize=(12, 14),
    sharex=True
)


# 1. 膝蓋
axes[0].plot(
    frames,
    left_knee,
    label="Left Knee"
)

axes[0].plot(
    frames,
    right_knee,
    label="Right Knee"
)

axes[0].set_ylabel("Angle (deg)")
axes[0].set_title("Knee Angle")
axes[0].legend()
axes[0].grid(True)


# 2. 肩膀與髖部
axes[1].plot(
    frames,
    shoulder,
    label="Shoulder"
)

axes[1].plot(
    frames,
    hip,
    label="Hip"
)

axes[1].set_ylabel("Angle (deg)")
axes[1].set_title("Shoulder and Hip Angle")
axes[1].legend()
axes[1].grid(True)


# 3. 手肘
axes[2].plot(
    frames,
    left_elbow,
    label="Left Elbow"
)

axes[2].plot(
    frames,
    right_elbow,
    label="Right Elbow"
)

axes[2].set_ylabel("Angle (deg)")
axes[2].set_title("Elbow Angle")
axes[2].legend()
axes[2].grid(True)


# 4. 步幅
axes[3].plot(
    frames,
    stride,
    label="Stride Distance"
)

axes[3].set_xlabel("Frame")
axes[3].set_ylabel("Distance")
axes[3].set_title("Stride Distance")
axes[3].legend()
axes[3].grid(True)


plt.suptitle(
    "Pitching Motion Features",
    fontsize=16
)

plt.tight_layout()

plt.savefig(OUTPUT_PATH)

plt.show()

print("所有動作特徵圖完成")
print(f"圖片已儲存：{OUTPUT_PATH}")