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
  var directionNames = {positive: "正", negative: "負", zero: "零", includes_zero: "含零", unavailable: "未定"};
  var roleNames = {throwing_elbow: "投球肘", lead_knee: "前導膝"};
  function profilePairs(data, timing) {
    return data.pairs.filter(function (pair) { return pair.timing_key === timing; });
  }
  function profileStageText(stage) {
    var lines = ["已確認時距涵蓋：" + durationText(stage.timing_envelope_seconds_fraction) +
      "；已確認球：" + (stage.timing_available_clip_ids.join("、") || "無") +
      "；事件未定球：" + (stage.timing_unavailable_clip_ids.join("、") || "無") + "。"];
    Object.keys(roleNames).forEach(function (role) {
      var joint = stage.joints[role];
      lines.push(roleNames[role] + "端點差方向：" + Object.keys(directionNames).map(function (direction) {
        return directionNames[direction] + "＝" + (joint.clip_ids_by_direction[direction].join("、") || "無");
      }).join("；") + "；全部球共同方向＝" + (directionNames[joint.common_direction] || "無") + "。");
    });
    lines.push("方向只描述模型XY端點差，不代表整段單調變化；逐點可靠性unknown，usable_for_analysis=null。");
    return lines.join(" ");
  }
  function profileJointTexts(stage, pitchId) {
    function count(value) { return value === null ? "未定" : String(value); }
    return Object.keys(roleNames).map(function (role) {
      var found = stage.joints[role].clip_summaries.filter(function (row) { return row.pitch_id === pitchId; });
      if (found.length !== 1) throw new RangeError("Expected one saved joint summary");
      var row = found[0], bounds = row.min_delta_deg === null || row.max_delta_deg === null ? "未定" :
        row.min_delta_deg.toFixed(6) + " 至 " + row.max_delta_deg.toFixed(6) + " 度";
      return roleNames[role] + "模型端點差：" + bounds + "；原分類：" + directionNames[row.delta_direction] +
        "；可算／全部端點配對：" + count(row.calculated_pairs) + "／" + count(row.total_pairs) +
        "；缺座標配對：" + count(row.missing_endpoint_pairs) + "；退化配對：" + count(row.degenerate_endpoint_pairs) +
        "。" + (row.calculated_pairs ? "可算不代表關節可信。" : row.transition_reason);
    });
  }
  var helpers = {selectedPair: selectedPair, eventTargets: eventTargets, eventUrl: eventUrl, durationText: durationText,
    profilePairs: profilePairs, profileStageText: profileStageText, profileJointTexts: profileJointTexts};
  if (typeof module !== "undefined" && module.exports) module.exports = helpers;
  if (typeof document === "undefined") return;
  function initialize() {
    var node = document.getElementById("timing-data");
    if (!node) return;
    var data = JSON.parse(node.textContent), stage = document.getElementById("timing-select"), navigationRequest = 0;
    var profile = data.mode === "same_pitcher_profile", pairSelect = profile ? document.getElementById("profile-pair-select") : null;
    var singleClip = profile && data.cohorts.length === 1;
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
      if (profile) {
        if (select.parentElement) select.parentElement.hidden = true;
      } else select.addEventListener("change", render);
    });
    function setProfilePair() {
      if (singleClip) return;
      var available = profilePairs(data, stage.value), index = Number(pairSelect.value);
      if (!Number.isSafeInteger(index) || index < 0 || index >= available.length) throw new RangeError("Invalid saved profile pair");
      document.getElementById("a-select").value = available[index].a_pitch_id;
      document.getElementById("b-select").value = available[index].b_pitch_id;
    }
    function refreshProfilePairs() {
      var a = document.getElementById("a-select").value, b = singleClip ? null : document.getElementById("b-select").value;
      var available = profilePairs(data, stage.value), previous = available.findIndex(function (pair) {
        return pair.a_pitch_id === a && pair.b_pitch_id === b;
      });
      pairSelect.replaceChildren();
      available.forEach(function (pair, index) { option(pairSelect, String(index), pair.a_pitch_id + " ／ " + pair.b_pitch_id); });
      pairSelect.disabled = singleClip;
      if (singleClip) {
        pairSelect.hidden = true;
        document.getElementById("b-panel").hidden = true;
      } else {
        pairSelect.value = String(previous >= 0 ? previous : 0);
        setProfilePair();
      }
    }
    function render() {
      var definition = data.stages.find(function (s) { return s.key === stage.value; });
      var a = document.getElementById("a-select").value, b = singleClip ? null : document.getElementById("b-select").value;
      if (singleClip) {
        var only = data.cohorts[0].clips[0].timing[stage.value];
        document.getElementById("pair-durations").textContent = "A：" + durationText(only.seconds_bounds_fraction);
        document.getElementById("pair-result").textContent = "單球：沒有跨球比較。";
        document.getElementById("pair-reasons").textContent = only.status === "unavailable" ? only.reason : "";
      } else {
        var pair = selectedPair(data, stage.value, a, b), values = pair.delta_seconds_bounds;
        document.getElementById("pair-durations").textContent = "A：" + durationText(pair.a_seconds_bounds_fraction) + "；B：" + durationText(pair.b_seconds_bounds_fraction);
        document.getElementById("pair-result").textContent = relationNames[pair.relation] + (values ?
          "；A−B＝" + values[0].toFixed(6) + " 至 " + values[1].toFixed(6) + " 秒（" + pair.delta_seconds_bounds_fraction.join(" 至 ") + "）。" : "。");
        document.getElementById("pair-reasons").textContent = Object.keys(pair.unavailable_reasons).filter(function (s) {
          return pair.unavailable_reasons[s];
        }).map(function (s) { return s.toUpperCase() + "：" + pair.unavailable_reasons[s]; }).join("；");
      }
      if (profile) document.getElementById("profile-stage-summary").textContent = profileStageText(definition);
      data.cohorts.forEach(function (cohort) {
        var side = cohort.side, id = side === "a" ? a : b;
        var clip = cohort.clips.find(function (c) { return c.pitch_id === id; });
        var player = document.getElementById(side + "-player"), buttons = document.getElementById(side + "-events");
        if (player.getAttribute("data-page") !== clip.page_url) {
          player.setAttribute("data-page", clip.page_url); player.src = clip.page_url;
        }
        var raw = document.getElementById(side + "-raw"); raw.href = clip.video_url;
        document.getElementById(side + "-fps").textContent = "原片FPS：" + clip.fps_fraction + "；格號由0開始。";
        if (profile) {
          var joints = document.getElementById(side + "-joints"); joints.replaceChildren();
          profileJointTexts(definition, id).forEach(function (text) {
            var line = document.createElement("p"); line.textContent = text; joints.appendChild(line);
          });
        }
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
    if (profile) {
      pairSelect.addEventListener("change", function () { setProfilePair(); render(); });
      stage.addEventListener("change", function () { refreshProfilePairs(); render(); });
      refreshProfilePairs();
    } else stage.addEventListener("change", render);
    render();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialize, {once: true});
  else initialize();
}(typeof window !== "undefined" ? window : globalThis));
