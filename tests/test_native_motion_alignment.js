"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { sourceFrameAt, segmentPoints, navigationState } = require("../src/pitch_analysis/review_assets/native_motion_alignment.js");

function fixture() {
  return {
    frame_count: 8, fps_fraction: "60000/1001", alignment_frame: 3,
    rows: Array.from({length: 8}, (_, frame) => ({
      frame_index: frame, timestamp_sec: frame * 1001 / 60000,
      throwing_elbow_model_xy_deg: 40 + frame,
      throwing_elbow_coordinate_status: "calculated_from_model_xy",
      lead_knee_model_xy_deg: 80 + frame,
      lead_knee_coordinate_status: "calculated_from_model_xy",
    })),
  };
}

function assertSegments(actual, expected) {
  assert.equal(actual.length, expected.length);
  actual.forEach((segment, index) => {
    assert.equal(segment.length, expected[index].length);
    segment.forEach((point, pointIndex) => {
      const target = expected[index][pointIndex];
      assert.ok(Math.abs(point[0] - target[0]) < 1e-12);
      assert.deepEqual(point.slice(1), target.slice(1));
    });
  });
}

test("fractional relative time identifies negative, zero, first and last original frames", () => {
  const clip = fixture();
  for (const frame of [0, 1, 2, 3, 4, 7]) {
    assert.equal(sourceFrameAt(clip, (frame - 3) * 1001 / 60000), frame);
  }
  assert.equal(sourceFrameAt(clip, -.49 * 1001 / 60000), 3);
  assert.equal(sourceFrameAt(clip, -.51 * 1001 / 60000), 2);
  assert.equal(sourceFrameAt(clip, .49 * 1001 / 60000), 3);
  assert.equal(sourceFrameAt(clip, .51 * 1001 / 60000), 4);
});

test("times outside one clip's saved range produce no clamped navigation target", () => {
  const clip = fixture();
  assert.equal(sourceFrameAt(clip, -4 * 1001 / 60000), null);
  assert.equal(sourceFrameAt(clip, 5 * 1001 / 60000), null);
  assert.equal(sourceFrameAt(clip, -.5), null);
  assert.equal(sourceFrameAt(clip, .5), null);
  const single = {frame_count: 1, fps_fraction: "60000/1001", alignment_frame: 0, rows: [clip.rows[0]]};
  assert.equal(sourceFrameAt(single, 0), 0);
  assert.equal(sourceFrameAt(single, 1001 / 60000), null);
});

test("segments preserve original angles and frames while missing and degenerate samples break lines", () => {
  const clip = fixture();
  clip.rows[2].throwing_elbow_model_xy_deg = null;
  clip.rows[2].throwing_elbow_coordinate_status = "missing_coordinates";
  clip.rows[4].throwing_elbow_model_xy_deg = null;
  clip.rows[4].throwing_elbow_coordinate_status = "degenerate_geometry";
  const before = structuredClone(clip);
  const point = frame => [(frame - 3) * 1001 / 60000, 40 + frame, frame];
  assertSegments(segmentPoints(clip, "throwing_elbow"), [[point(0), point(1)], [point(3)], [point(5), point(6), point(7)]]);
  const knee = segmentPoints(clip, "lead_knee");
  assert.equal(knee.length, 1);
  assertSegments(knee, [clip.rows.map(row => [(row.frame_index - 3) * 1001 / 60000,
    row.lead_knee_model_xy_deg, row.frame_index])]);
  assert.deepEqual(clip, before);
  clip.rows.forEach(row => { row.throwing_elbow_model_xy_deg = null; row.throwing_elbow_coordinate_status = "missing_coordinates"; });
  assert.deepEqual(segmentPoints(clip, "throwing_elbow"), []);
});

test("loading another clip cannot consume the latest pending source-frame request", () => {
  const state = navigationState();
  state.request(0, 12);
  state.request(1, 24);
  assert.equal(state.ready(0, true), null);
  assert.equal(state.ready(1, false), null);
  assert.deepEqual(state.ready(1, true), {clipIndex: 1, frame: 24});
  assert.equal(state.ready(1, true), null);
  state.request(1, 25);
  state.request(1, 26);
  assert.deepEqual(state.ready(1, true), {clipIndex: 1, frame: 26});
});

test("manual clip selection cancels stale requests while selecting the requested clip preserves it", () => {
  const state = navigationState();
  state.request(1, 24);
  state.selected(1);
  assert.deepEqual(state.ready(1, true), {clipIndex: 1, frame: 24});
  state.request(1, 25);
  state.selected(0);
  assert.equal(state.ready(1, true), null);
  state.request(0, 7);
  state.cancel();
  assert.equal(state.ready(0, true), null);
});
