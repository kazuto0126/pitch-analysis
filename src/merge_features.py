import csv


INPUT_FILES = {
    "knee": "data/pose_data/test_pitch_angles.csv",
    "shoulder": "data/pose_data/test_pitch_shoulder_angles.csv",
    "elbow": "data/pose_data/test_pitch_elbow_angles.csv",
    "hip": "data/pose_data/test_pitch_hip_angles.csv",
    "stride": "data/pose_data/test_pitch_stride.csv",
}

OUTPUT_PATH = "data/pose_data/test_pitch_features.csv"


def read_csv(path):
    data = {}

    with open(path, "r", encoding="utf-8-sig") as file:

        reader = csv.DictReader(file)

        for row in reader:

            frame = int(row["frame"])

            if frame not in data:
                data[frame] = {}

            for key, value in row.items():

                if key != "frame":
                    data[frame][key] = value

    return data


all_features = {}

for feature_name, path in INPUT_FILES.items():

    feature_data = read_csv(path)

    for frame, values in feature_data.items():

        if frame not in all_features:
            all_features[frame] = {}

        for key, value in values.items():

            all_features[frame][key] = value


output_columns = [
    "frame",
    "left_knee_angle",
    "right_knee_angle",
    "shoulder_angle",
    "left_elbow_angle",
    "right_elbow_angle",
    "hip_angle",
    "stride_distance",
]


with open(
    OUTPUT_PATH,
    "w",
    newline="",
    encoding="utf-8-sig"
) as file:

    writer = csv.writer(file)

    writer.writerow(output_columns)

    for frame in sorted(all_features):

        row = [frame]

        for column in output_columns[1:]:

            row.append(
                all_features[frame].get(column, "")
            )

        writer.writerow(row)


print("特徵整合完成")
print(f"輸出檔案：{OUTPUT_PATH}")