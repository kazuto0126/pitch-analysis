"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { frameIndexForMediaTime, seekTimeForFrame } = require("../src/pitch_analysis/review_assets/native_motion_viewer.js");

test("presented fractional timestamps identify first, adjacent and last source frames", () => {
  for (const [fraction, fps, count] of [["60000/1001", 60000 / 1001, 335], ["30/1", 30, 87]]) {
    for (const index of [0, 1, 2, 33, count - 2, count - 1]) {
      assert.equal(frameIndexForMediaTime(index / fps, fraction, count, false), index);
    }
  }
});

test("seeking stays inside the requested source frame interval", () => {
  for (const [fraction, fps, count] of [["60000/1001", 60000 / 1001, 335], ["30", 30, 87]]) {
    for (const index of [0, 1, 2, 33, count - 1]) {
      const time = seekTimeForFrame(index, fraction, count);
      assert.ok(time > index / fps && time < (index + 1) / fps);
      assert.equal(frameIndexForMediaTime(time, fraction, count, true), index);
    }
  }
});

test("presentation timestamps and estimated playback positions have distinct rounding", () => {
  assert.equal(frameIndexForMediaTime(1.75 / 30, "30", 87, false), 2);
  assert.equal(frameIndexForMediaTime(1.75 / 30, "30", 87, true), 1);
});

test("navigation clamps both ends and supports a one-frame source", () => {
  assert.equal(frameIndexForMediaTime(-1, "30", 87), 0);
  assert.equal(frameIndexForMediaTime(99, "30", 87), 86);
  assert.equal(seekTimeForFrame(-5, "30", 87), .25 / 30);
  assert.equal(seekTimeForFrame(999, "30", 87), 86.25 / 30);
  assert.equal(frameIndexForMediaTime(100, "30", 1), 0);
  assert.equal(seekTimeForFrame(1, "30", 1), .25 / 30);
});

test("invalid times, rates and frame counts are rejected instead of silently jumping", () => {
  for (const rate of ["0", "30/0", "-30", "not-fps", Infinity]) {
    assert.throws(() => frameIndexForMediaTime(0, rate, 3));
  }
  for (const count of [0, -1, 1.5, Infinity]) {
    assert.throws(() => frameIndexForMediaTime(0, "30", count));
  }
  assert.throws(() => frameIndexForMediaTime(NaN, "30", 3));
  assert.throws(() => seekTimeForFrame(Infinity, "30", 3));
});
