import csv
import matplotlib.pyplot as plt


INPUT_PATH = "data/pose_data/test_pitch_elbow_angles.csv"
OUTPUT_PATH = "data/pose_data/elbow_angles.png"


frames = []
left_angles = []
right_angles = []


with open(INPUT_PATH, "r", encoding="utf-8-sig") as file:

    reader = csv.DictReader(file)

    for row in reader:

        frames.append(int(row["frame"]))

        if row["left_elbow_angle"]:
            left_angles.append(float(row["left_elbow_angle"]))
        else:
            left_angles.append(None)

        if row["right_elbow_angle"]:
            right_angles.append(float(row["right_elbow_angle"]))
        else:
            right_angles.append(None)


plt.figure(figsize=(12, 6))

plt.plot(
    frames,
    left_angles,
    label="Left Elbow"
)

plt.plot(
    frames,
    right_angles,
    label="Right Elbow"
)

plt.xlabel("Frame")
plt.ylabel("Elbow Angle (degrees)")
plt.title("Elbow Angle During Pitching Motion")

plt.legend()
plt.grid(True)

plt.tight_layout()

plt.savefig(OUTPUT_PATH)

plt.show()

print("手肘角度圖完成")
print(f"圖片已儲存：{OUTPUT_PATH}")
