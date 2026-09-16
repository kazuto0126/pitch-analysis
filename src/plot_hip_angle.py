import csv
import matplotlib.pyplot as plt


INPUT_PATH = "data/pose_data/test_pitch_hip_angles.csv"
OUTPUT_PATH = "data/pose_data/hip_angles.png"


frames = []
hip_angles = []


with open(INPUT_PATH, "r", encoding="utf-8-sig") as file:

    reader = csv.DictReader(file)

    for row in reader:

        frames.append(int(row["frame"]))

        if row["hip_angle"]:
            hip_angles.append(float(row["hip_angle"]))
        else:
            hip_angles.append(None)


plt.figure(figsize=(12, 6))

plt.plot(
    frames,
    hip_angles,
    label="Hip Angle"
)

plt.xlabel("Frame")
plt.ylabel("Hip Angle (degrees)")
plt.title("Hip Angle During Pitching Motion")

plt.legend()
plt.grid(True)

plt.tight_layout()

plt.savefig(OUTPUT_PATH)

plt.show()

print("髖部角度圖完成")
print(f"圖片已儲存：{OUTPUT_PATH}")