"""Export source-bound raw/marked images and blank human query notes only."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def choose_queries(features):
    """One deterministic representative per saved frame-FB rank group."""
    chosen = []
    for group in range(4):
        members = sorted((r for r in features if r['fb_per_frame_group'] == group),
                         key=lambda r: (r['fb_error_px'], r['feature_id']))
        if members:
            chosen.append(members[(len(members)-1)//2])
    return chosen


def export(measurement_root, pitch, indices, output):
    if output.exists():
        raise FileExistsError(f'Fresh output required: {output}')
    source = measurement_root / 'feature_validity_measurements.json'
    data = read(source)
    if data['human_annotation_inputs'] or data['warning_predictions_generated']:
        raise ValueError('Expected saved, annotation-free numerical measurements')
    clip = next(c for c in data['clips'] if c['pitch_id'] == pitch)
    if any(not 0 <= i < clip['total_frames'] for i in indices) or len(set(indices)) != len(indices):
        raise ValueError('Invalid or duplicate frame index')
    video_path = Path(clip['source_video']['path'])
    if sha(video_path) != clip['source_video']['sha256']:
        raise ValueError('Source video changed')
    for path, expected in data['source_hashes'].items():
        if sha(path) != expected:
            raise ValueError('Saved measurement source changed')
    source_before = sha(source)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 20)
    bold = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 25)
    small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
    palette = ['#ffcf39', '#43d5ff', '#ff6596', '#ac9cff']
    output.mkdir(parents=True)
    raw_root = output / 'raw_frames'
    raw_root.mkdir()
    rows, files = [], []
    reader = cv2.VideoCapture(str(video_path))
    try:
        for index in range(clip['total_frames']):
            ok, pixels = reader.read()
            if not ok or pixels.shape[:2] != (clip['height'], clip['width']):
                raise ValueError('Source image timeline/dimensions mismatch')
            if index not in indices:
                continue
            raw = Image.fromarray(cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB))
            raw_name = f'{pitch}_frame_{index:04d}.png'
            raw_path = raw_root / raw_name
            raw.save(raw_path)
            marked = raw.copy()
            draw = ImageDraw.Draw(marked)
            selected = choose_queries(clip['frames'][index]['features'])
            for number, feature in enumerate(selected, 1):
                x, y = feature['current_xy_px']
                color = palette[number-1]
                # Center stays visible; only the ring and offset number are drawn.
                draw.ellipse((x-9, y-9, x+9, y+9), outline='black', width=5)
                draw.ellipse((x-9, y-9, x+9, y+9), outline=color, width=3)
                tx, ty = min(max(x+13, 3), clip['width']-25), min(max(y-14, 3), clip['height']-30)
                draw.text((tx, ty), str(number), font=bold, fill=color, stroke_width=2, stroke_fill='black')
                rows.append(dict(query_id=f'{pitch}_f{index:04d}_q{number}', pitch_id=pitch,
                                 frame_index=index, timestamp_ms=clip['frames'][index]['timestamp_ms'],
                                 display_number=number, saved_feature_id=feature['feature_id'],
                                 queried_image_xy_px=[x,y], source_raw_image=raw_name,
                                 source_raw_image_sha256=sha(raw_path), human_status='unreviewed',
                                 human_body_region=None, confidence=None, reviewer_note=None))
            width, height = clip['width'], clip['height']
            panel = Image.new('RGB', (2*width, height+425), '#111723')
            title = ImageDraw.Draw(panel)
            title.text((12,8), f'{pitch} | frame {index} | only {len(selected)} IMAGE FEATURE queries', font=bold, fill='white')
            title.text((12,43), 'Left: original image    Right: ring center is the query position', font=font, fill='white')
            panel.paste(raw, (0,80))
            panel.paste(marked, (width,80))
            for number, feature in enumerate(selected, 1):
                x, y = feature['current_xy_px']
                left, top = math.floor(x)-32, math.floor(y)-32
                crop = raw.crop((left,top,left+64,top+64)).resize((208,208),Image.Resampling.NEAREST)
                cd = ImageDraw.Draw(crop)
                cx, cy = (x-left)*208/64, (y-top)*208/64
                cd.ellipse((cx-13,cy-13,cx+13,cy+13),outline='black',width=5)
                cd.ellipse((cx-13,cy-13,cx+13,cy+13),outline=palette[number-1],width=3)
                cell = (number-1)*(2*width//4)
                title.text((cell+12,height+92),f'Query {number}: exact center',font=font,fill=palette[number-1])
                panel.paste(crop,(cell+12,height+126))
            title.text((12,height+351), 'T torso | P other visible pitcher part | O other person/background | ? uncertain', font=small, fill='white')
            title.text((12,height+380), 'These points are not joints. No human answers or model-mask predictions are filled.', font=small, fill='white')
            display_path = output / f'{pitch}_frame_{index:04d}_review.png'
            panel.save(display_path)
            files.append(dict(frame_index=index, raw_image=str(raw_path), raw_sha256=sha(raw_path),
                              display_image=str(display_path), display_sha256=sha(display_path)))
    finally:
        reader.release()
    if sha(source) != source_before or sha(video_path) != clip['source_video']['sha256']:
        raise ValueError('Source changed during export')
    manifest = dict(purpose='Blank human image-feature membership queries; no pose GT edits',
                    source_video=clip['source_video'], width=clip['width'], height=clip['height'],
                    total_frames=clip['total_frames'], measurement_file=str(source), measurement_sha256=source_before,
                    generator_code_sha256=sha(__file__), selection_rule='Median-position record in each saved per-frame FB rank group; empty groups skipped',
                    inspected_frames=sorted(indices), queries=rows, files=files,
                    human_review_status='unreviewed', reviewer=None, reviewed_at_utc=None,
                    ground_truth_modified=False, new_model_inference=False,
                    limits=['Sparse query membership is not full-body segmentation, all-feature or full-clip validation.',
                            'Quality rank is hidden in the display and is not a human answer.',
                            'Human uncertainty is allowed; no projection behind occlusion.'])
    (output / 'query_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    notes = ['# 人工特徵歸屬試看：先8點', '',
             '這是影像特徵的位置問題，不是關節標註。已完成的12關節保持原樣。', '',
             '- T：圓圈中心在投手可見的軀幹／軀幹衣物上。',
             '- P：在投手其他可見部位，如頭、手臂、腿或手套。',
             '- O：在其他人或背景上；可補充打者、捕手、裁判、草地等。',
             '- ?：被擋住、模糊、跨邊界或不能判斷。不要猜透視位置。', '',
             '左圖可檢查原像素。右圖只標圓圈中心與題號，沒有畫AI骨架或填答案。', '',
             '直接回覆例：「86：1=T、2=P、3=O、4=?」。例子不是實際答案。', '',
             'Reviewer：待本人提供；完成時間：待本人提供；confidence：未提供保持空白。', '',
             '| Frame | 題號 | 人工答案 | 備註 |', '|---|---|---|---|']
    notes += [f'| {r["frame_index"]} | {r["display_number"]} | 未覆核 | |' for r in rows]
    (output / 'REVIEW_NOTES.md').write_text('\n'.join(notes)+'\n',encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('measurement_root',type=Path)
    parser.add_argument('pitch_id')
    parser.add_argument('output_root',type=Path)
    parser.add_argument('--frames',nargs='+',type=int,required=True)
    args=parser.parse_args()
    result=export(args.measurement_root,args.pitch_id,args.frames,args.output_root)
    print(json.dumps(dict(status='human_answers_unreviewed', frames=result['inspected_frames'], queries=len(result['queries']))))
