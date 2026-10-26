/* Read-only timing-pair selection; independent source-frame players, no time warp. */
(function (global) {
  "use strict";
  function selectedPair(data, timing, a, b) {
    var found = data.pairs.filter(function (p) { return p.timing_key === timing && p.a_pitch_id === a && p.b_pitch_id === b; });
    if (found.length !== 1) throw new RangeError("Expected one saved timing pair");
    return found[0];
  }
  function eventTargets(clip, name) {
    var event = clip.events[name];
    if (!event || event.status !== "annotated" || !Array.isArray(event.frame_bounds)) return [];
    var bounds = event.frame_bounds;
    if (bounds.length !== 2 || bounds.some(function (v) { return !Number.isSafeInteger(v) || v < 0 || v >= clip.frame_count; }) || bounds[0] > bounds[1]) {
      throw new RangeError("Invalid source event bounds");
    }
    return bounds[0] === bounds[1] ? [{frame: bounds[0], label: "已確認格"}] :
      [{frame: bounds[0], label: "範圍下界"}, {frame: bounds[1], label: "範圍上界"}];
  }
  function eventUrl(clip, frame, request) {
    if (!Number.isSafeInteger(frame) || frame < 0 || frame >= clip.frame_count) throw new RangeError("Invalid source frame");
    if (request !== undefined && (!Number.isSafeInteger(request) || request < 1)) throw new RangeError("Invalid navigation request");
    return clip.page_url + "#frame=" + frame + (request === undefined ? "" : "&request=" + request);
  }
  function durationText(values) {
    if (values === null) return "未定";
    return values.map(function (value) {
      var parts = value.split("/");
      return (Number(parts[0]) / (parts.length === 2 ? Number(parts[1]) : 1)).toFixed(6);
    }).join(" 至 ") + " 秒";
  }
  var helpers = {selectedPair: selectedPair, eventTargets: eventTargets, eventUrl: eventUrl, durationText: durationText};
  if (typeof module !== "undefined" && module.exports) module.exports = helpers;
  if (typeof document === "undefined") return;
  function initialize() {
    var node = document.getElementById("timing-data");
    if (!node) return;
    var data = JSON.parse(node.textContent), stage = document.getElementById("timing-select"), navigationRequest = 0;
    var relationNames = {a_shorter: "A時距較短", a_longer: "A時距較長", identical_exact: "精確時距相同",
      touching: "範圍相接，無嚴格先後", overlapping: "範圍重疊，無嚴格先後", unavailable: "事件不足，差值未定"};
    function option(select, value, label) {
      var item = document.createElement("option"); item.value = value; item.textContent = label; select.appendChild(item);
    }
    data.stages.forEach(function (s) { option(stage, s.key, s.label); });
    stage.value = "foot_plant_to_release";
    data.cohorts.forEach(function (cohort) {
      var side = cohort.side, select = document.getElementById(side + "-select");
      document.getElementById(side + "-heading").textContent = side.toUpperCase() + "：" + cohort.pitcher_id;
      cohort.clips.forEach(function (clip) { option(select, clip.pitch_id, clip.pitch_id); });
      select.addEventListener("change", render);
    });
    function render() {
      var definition = data.stages.find(function (s) { return s.key === stage.value; });
      var a = document.getElementById("a-select").value, b = document.getElementById("b-select").value;
      var pair = selectedPair(data, stage.value, a, b), values = pair.delta_seconds_bounds;
      document.getElementById("pair-durations").textContent = "A：" + durationText(pair.a_seconds_bounds_fraction) + "；B：" + durationText(pair.b_seconds_bounds_fraction);
      document.getElementById("pair-result").textContent = relationNames[pair.relation] + (values ?
        "；A−B＝" + values[0].toFixed(6) + " 至 " + values[1].toFixed(6) + " 秒（" + pair.delta_seconds_bounds_fraction.join(" 至 ") + "）。" : "。");
      document.getElementById("pair-reasons").textContent = Object.keys(pair.unavailable_reasons).filter(function (s) {
        return pair.unavailable_reasons[s];
      }).map(function (s) { return s.toUpperCase() + "：" + pair.unavailable_reasons[s]; }).join("；");
      data.cohorts.forEach(function (cohort) {
        var side = cohort.side, id = side === "a" ? a : b;
        var clip = cohort.clips.find(function (c) { return c.pitch_id === id; });
        var player = document.getElementById(side + "-player"), buttons = document.getElementById(side + "-events");
        if (player.getAttribute("data-page") !== clip.page_url) {
          player.setAttribute("data-page", clip.page_url); player.src = clip.page_url;
        }
        var raw = document.getElementById(side + "-raw"); raw.href = clip.video_url;
        document.getElementById(side + "-fps").textContent = "原片FPS：" + clip.fps_fraction + "；格號由0開始。";
        buttons.replaceChildren();
        [[definition.start, "起點"], [definition.end, "終點"]].forEach(function (entry) {
          var event = clip.events[entry[0]], line = document.createElement("p");
          var targets = eventTargets(clip, entry[0]);
          line.textContent = entry[1] + "：" + (targets.length ? event.frame_bounds.join("–") + " 格 " : "未確認／不可觀測，不自動定位。 ");
          targets.forEach(function (target) {
            var button = document.createElement("button"); button.type = "button";
            button.textContent = target.label + " " + target.frame + " 格";
            button.addEventListener("click", function () { player.src = eventUrl(clip, target.frame, ++navigationRequest); });
            line.appendChild(button);
          });
          buttons.appendChild(line);
        });
      });
    }
    stage.addEventListener("change", render);
    render();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialize, {once: true});
  else initialize();
}(typeof window !== "undefined" ? window : globalThis));
