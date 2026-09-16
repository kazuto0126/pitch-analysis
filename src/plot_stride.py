import csv
import matplotlib.pyplot as plt


INPUT_PATH = "data/pose_data/test_pitch_stride.csv"
OUTPUT_PATH = "data/pose_data/stride.png"


frames = []
stride_distances = []


with open(INPUT_PATH, "r", encoding="utf-8-sig") as file:

    reader = csv.DictReader(file)

    for row in reader:

        frames.append(int(row["frame"]))

        if row["stride_distance"]:
            stride_distances.append(float(row["stride_distance"]))
        else:
            stride_distances.append(None)


plt.figure(figsize=(12, 6))

plt.plot(
    frames,
    stride_distances,
    label="Stride Distance"
)

plt.xlabel("Frame")
plt.ylabel("Stride Distance (normalized)")
plt.title("Stride Distance During Pitching Motion")

plt.legend()
plt.grid(True)

plt.tight_layout()

plt.savefig(OUTPUT_PATH)

plt.show()

print("步幅圖完成")
print(f"圖片已儲存：{OUTPUT_PATH}")