import cv2
import csv
import mediapipe as mp


VIDEO_PATH = "data/raw_videos/test_pitch.mp4"
MODEL_PATH = "models/pose_landmarker_full.task"
OUTPUT_PATH = "data/pose_data/test_pitch_pose.csv"


BaseOptions = mp.tasks.BaseOptions
PoseLandmarker = mp.tasks.vision.PoseLandmarker
PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode


options = PoseLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=VisionRunningMode.VIDEO,
    num_poses=1,
    min_pose_detection_confidence=0.5,
    min_pose_presence_confidence=0.5,
    min_tracking_confidence=0.5,
)


cap = cv2.VideoCapture(VIDEO_PATH)

if not cap.isOpened():
    print("無法開啟影片")
    exit()


fps = cap.get(cv2.CAP_PROP_FPS)

print("影片開啟成功")
print(f"FPS：{fps}")


with open(OUTPUT_PATH, "w", newline="", encoding="utf-8-sig") as csv_file:

    writer = csv.writer(csv_file)

    writer.writerow([
        "frame",
        "timestamp_ms",
        "landmark",
        "x",
        "y",
        "z",
        "visibility"
    ])

    with PoseLandmarker.create_from_options(options) as landmarker:

        frame_index = 0

        while True:

            ret, frame = cap.read()

            if not ret:
                break

            rgb_frame = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB
            )

            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb_frame
            )

            timestamp_ms = int(frame_index * 1000 / fps)

            result = landmarker.detect_for_video(
                mp_image,
                timestamp_ms
            )

            if result.pose_landmarks:

                landmarks = result.pose_landmarks[0]

                for landmark_index, landmark in enumerate(landmarks):

                    writer.writerow([
                        frame_index,
                        timestamp_ms,
                        landmark_index,
                        landmark.x,
                        landmark.y,
                        landmark.z,
                        landmark.visibility
                    ])

                print(
                    f"第 {frame_index} 幀："
                    f"偵測到 1 個人體，"
                    f"已儲存 {len(landmarks)} 個關節"
                )

            frame_index += 1


cap.release()

print()
print(f"總共處理 {frame_index} 幀")
print(f"姿態資料已儲存：{OUTPUT_PATH}")
print("程式結束")