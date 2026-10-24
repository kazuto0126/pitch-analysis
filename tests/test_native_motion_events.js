"use strict";
const assert = require("node:assert/strict");
const helpers = require("../src/pitch_analysis/review_assets/native_motion_events.js");
let checks = 0;
function eq(actual, expected) { assert.deepEqual(actual, expected); checks++; }
const exact = helpers.eventMarkerGeometry({marker_kind: "exact", frame_bounds: [0, 0]}, 87);
eq([exact.kind, exact.x0, exact.x1, exact.dashed], ["exact", 64, 64, false]);
const last = helpers.eventMarkerGeometry({marker_kind: "exact", frame_bounds: [86, 86]}, 87);
eq(last.x0, 940);
const candidate = helpers.eventMarkerGeometry({marker_kind: "uncertain", frame_bounds: [39, 39]}, 87);
eq([candidate.kind, candidate.singleFrame, candidate.dashed], ["uncertain", true, true]);
assert.match(helpers.eventFrameText({marker_kind: "uncertain", frame_bounds: [39, 39]}), /候選.*39.*不確定/);checks++;
const range = helpers.eventMarkerGeometry({marker_kind: "range", frame_bounds: [12, 18]}, 87);
assert.ok(range.bandLeft < range.x0 && range.bandRight > range.x1);checks++;
eq(range.dashed, false);
const uncertainRange = helpers.eventMarkerGeometry({marker_kind: "uncertain", frame_bounds: [38, 40]}, 87);
eq(uncertainRange.dashed, true);
eq(helpers.eventMarkerGeometry({marker_kind: "uncertain", frame_bounds: null}, 87), null);
eq(helpers.eventMarkerGeometry({marker_kind: "not_observable", frame_bounds: null}, 87), null);
assert.match(helpers.eventFrameText({marker_kind: "not_observable", frame_bounds: null}), /不可觀測/);checks++;
for (const event of [{marker_kind: "exact", frame_bounds: [1, 2]}, {marker_kind: "range", frame_bounds: [-1, 2]},
                     {marker_kind: "uncertain", frame_bounds: [0, 87]}]) {
  assert.throws(() => helpers.eventMarkerGeometry(event, 87), RangeError);checks++;
}
eq(helpers.eventMarkerGeometry({marker_kind: "exact", frame_bounds: [0, 0]}, 1).x0, 64);
assert.match(helpers.timingText({status:"bounded",seconds_bounds:[.1,.2],frame_bounds:[3,6],reason:"human range"}), /上下界 0\.1000–0\.2000 秒；3–6 格/);checks++;
assert.match(helpers.timingText({status:"unavailable",seconds_bounds:null,frame_bounds:null,reason:"uncertain"}), /無法界定.*uncertain/);checks++;
assert.match(helpers.windowText({status:"descriptive_model_xy_window",total_frames:3,calculated_frames:2,missing_frames:1,
  degenerate_frames:0,min_deg:44,max_deg:91,usable_deg:null}), /44\.0–91\.0°.*計算 2\/3.*缺失 1.*可用性未知/);checks++;
assert.match(helpers.windowText({status:"unavailable",total_frames:2,calculated_frames:0,missing_frames:2,
  degenerate_frames:0,min_deg:null,max_deg:null,usable_deg:null}), /未算出角度.*計算 0\/2/);checks++;
console.log(JSON.stringify({pure_event_ui_checks:checks,result:"passed",browser_or_DOM_used:false}));
