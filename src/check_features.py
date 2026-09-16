import csv


INPUT_PATH = "data/pose_data/test_pitch_features.csv"


with open(INPUT_PATH, "r", encoding="utf-8-sig") as file:

    reader = csv.DictReader(file)

    rows = list(reader)


print("特徵資料檢查")
print("=" * 50)

print(f"總影格數：{len(rows)}")

print("\n欄位：")
for column in reader.fieldnames:
    print(f"- {column}")


print("\n前 5 筆資料：")

for row in rows[:5]:

    print(row)


print("\n最後 5 筆資料：")

for row in rows[-5:]:

    print(row)