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
const singleReadout = helpers.windowText({status:"descriptive_model_xy_window",total_frames:1,calculated_frames:1,
  missing_frames:0,degenerate_frames:0,min_deg:44,max_deg:44,usable_deg:null,
  reading_kind:"single_frame",sample_span_deg:null,sample_span_scope:"not_assessable"});
assert.match(singleReadout, /單格視窗.*敏感度未評估/);checks++;
assert.doesNotMatch(singleReadout, /跨度\s*0(?:\.0)?°/);checks++;
assert.match(singleReadout, /計算 1\/1.*缺失 0.*退化 0.*可用性未知/);checks++;
const completeReadout = helpers.windowText({status:"descriptive_model_xy_window",total_frames:3,calculated_frames:3,
  missing_frames:0,degenerate_frames:0,min_deg:44,max_deg:91,usable_deg:null,
  reading_kind:"multiple_frames",sample_span_deg:47,sample_span_scope:"complete_window"});
assert.match(completeReadout, /窗內模型跨度 47\.0°.*可用性未知/);checks++;
const partialReadout = helpers.windowText({status:"descriptive_model_xy_window",total_frames:4,calculated_frames:2,
  missing_frames:1,degenerate_frames:1,min_deg:44,max_deg:91,usable_deg:null,
  reading_kind:"multiple_frames",sample_span_deg:47,sample_span_scope:"calculated_samples_only"});
assert.match(partialReadout, /可計算樣本跨度 47\.0°.*視窗不完整.*計算 2\/4.*缺失 1.*退化 1.*可用性未知/);checks++;
assert.doesNotMatch(partialReadout, /窗內模型跨度/);checks++;
const insufficientReadout = helpers.windowText({status:"descriptive_model_xy_window",total_frames:3,calculated_frames:1,
  missing_frames:1,degenerate_frames:1,min_deg:44,max_deg:44,usable_deg:null,
  reading_kind:"multiple_frames",sample_span_deg:null,sample_span_scope:"not_assessable"});
assert.match(insufficientReadout, /多格視窗.*跨度未估.*計算 1\/3.*可用性未知/);checks++;
assert.doesNotMatch(insufficientReadout, /跨度\s*0(?:\.0)?°/);checks++;
const zeroReadout = helpers.windowText({status:"descriptive_model_xy_window",total_frames:3,calculated_frames:3,
  missing_frames:0,degenerate_frames:0,min_deg:44,max_deg:44,usable_deg:null,
  reading_kind:"multiple_frames",sample_span_deg:0,sample_span_scope:"complete_window"});
assert.match(zeroReadout, /窗內模型跨度 0\.0°.*可用性未知/);checks++;
assert.doesNotMatch(zeroReadout, /可靠|穩定|可信/);checks++;
const legacyCompleteReadout = helpers.windowText({status:"descriptive_model_xy_window",total_frames:3,calculated_frames:3,
  missing_frames:0,degenerate_frames:0,min_deg:44,max_deg:91,usable_deg:null});
assert.match(legacyCompleteReadout, /窗內模型跨度 47\.0°/);checks++;
const legacyPartialReadout = helpers.windowText({status:"descriptive_model_xy_window",total_frames:3,calculated_frames:2,
  missing_frames:1,degenerate_frames:0,min_deg:44,max_deg:91,usable_deg:null});
assert.match(legacyPartialReadout, /可計算樣本跨度 47\.0°.*視窗不完整/);checks++;
const legacySingleReadout = helpers.windowText({status:"descriptive_model_xy_window",total_frames:1,calculated_frames:1,
  missing_frames:0,degenerate_frames:0,min_deg:44,max_deg:44,usable_deg:null});
assert.match(legacySingleReadout, /單格視窗.*敏感度未評估/);checks++;
assert.doesNotMatch(legacySingleReadout, /跨度\s*0(?:\.0)?°/);checks++;
const explicitNullReadout = helpers.windowText({status:"descriptive_model_xy_window",total_frames:3,calculated_frames:3,
  missing_frames:0,degenerate_frames:0,min_deg:44,max_deg:91,usable_deg:null,
  reading_kind:"multiple_frames",sample_span_deg:null,sample_span_scope:"not_assessable"});
assert.match(explicitNullReadout, /多格視窗.*跨度未估/);checks++;
assert.doesNotMatch(explicitNullReadout, /跨度 47\.0°/);checks++;
console.log(JSON.stringify({pure_event_ui_checks:checks,result:"passed",browser_or_DOM_used:false}));
