import csv


POSE_PATH = "data/pose_data/test_pitch_pose_named.csv"
FEATURE_PATH = "data/pose_data/test_pitch_features.csv"


def get_frames(path):
    frames = set()

    with open(path, "r", encoding="utf-8-sig") as file:

        reader = csv.DictReader(file)

        for row in reader:
            frames.add(int(row["frame"]))

    return frames


pose_frames = get_frames(POSE_PATH)
feature_frames = get_frames(FEATURE_PATH)

missing_frames = sorted(
    pose_frames - feature_frames
)


print("影格資料檢查")
print("=" * 50)

print(f"姿態資料影格數：{len(pose_frames)}")
print(f"特徵資料影格數：{len(feature_frames)}")
print(f"缺少影格數：{len(missing_frames)}")

print("\n缺少的影格：")

if missing_frames:

    print(missing_frames)

else:

    print("沒有缺少影格")