import csv

from landmark_names import LANDMARK_NAMES


INPUT_PATH = "data/pose_data/test_pitch_pose.csv"
OUTPUT_PATH = "data/pose_data/test_pitch_pose_named.csv"


with open(INPUT_PATH, "r", encoding="utf-8-sig") as input_file:
    reader = csv.DictReader(input_file)

    fieldnames = reader.fieldnames

    with open(
        OUTPUT_PATH,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as output_file:

        writer = csv.DictWriter(
            output_file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for row in reader:

            landmark_index = int(row["landmark"])

            row["landmark"] = LANDMARK_NAMES.get(
                landmark_index,
                f"LANDMARK_{landmark_index}"
            )

            writer.writerow(row)


print("關節名稱轉換完成")
print(f"輸出檔案：{OUTPUT_PATH}")