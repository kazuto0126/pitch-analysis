import csv
import matplotlib.pyplot as plt


INPUT_PATH = "data/pose_data/test_pitch_shoulder_angles.csv"
OUTPUT_PATH = "data/pose_data/shoulder_angles.png"


frames = []
shoulder_angles = []


with open(INPUT_PATH, "r", encoding="utf-8-sig") as file:

    reader = csv.DictReader(file)

    for row in reader:

        frames.append(int(row["frame"]))

        if row["shoulder_angle"]:
            shoulder_angles.append(float(row["shoulder_angle"]))
        else:
            shoulder_angles.append(None)


plt.figure(figsize=(12, 6))

plt.plot(
    frames,
    shoulder_angles,
    label="Shoulder Angle"
)

plt.xlabel("Frame")
plt.ylabel("Shoulder Angle (degrees)")
plt.title("Shoulder Angle During Pitching Motion")

plt.legend()
plt.grid(True)

plt.tight_layout()

plt.savefig(OUTPUT_PATH)

plt.show()

print("肩膀角度圖完成")
print(f"圖片已儲存：{OUTPUT_PATH}")