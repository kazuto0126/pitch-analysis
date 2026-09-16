import cv2

video_path = "data/raw_videos/test_pitch.mp4"

cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print("無法開啟影片")
else:
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print("影片讀取成功！")
    print(f"FPS：{fps}")
    print(f"解析度：{width} x {height}")
    print(f"總幀數：{frame_count}")

cap.release()