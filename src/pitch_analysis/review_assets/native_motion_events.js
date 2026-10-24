/* Decorate the unchanged saved-motion viewer with supplied human event bounds. */
(function (global) {
  "use strict";

  var eventNames = ["preparation_start", "leg_lift", "foot_plant", "approximate_release", "follow_through_end"];
  var eventLabels = {
    preparation_start: "準備／啟動", leg_lift: "最高抬腿", foot_plant: "前腳落地",
    approximate_release: "近似出手", follow_through_end: "收尾結束"
  };
  var timingNames = ["preparation_to_leg_lift", "leg_lift_to_foot_plant", "foot_plant_to_release", "release_to_follow_through_end"];
  var timingLabels = ["準備 → 最高抬腿", "最高抬腿 → 落地", "落地 → 近似出手", "近似出手 → 收尾"];
  var colors = ["#626f85", "#7749aa", "#19836c", "#bc3d49", "#926224"];
  var left = 64, right = 940, top = 20, bottom = 216;

  function eventMarkerGeometry(event, count) {
    if (!Number.isSafeInteger(count) || count < 1) throw new RangeError("Invalid source frame count");
    var kind = event.marker_kind;
    if (["exact", "range", "uncertain", "not_observable"].indexOf(kind) < 0) throw new RangeError("Unknown marker kind");
    var bounds = event.frame_bounds;
    if (kind === "not_observable" || bounds === null || bounds === undefined) return null;
    if (!Array.isArray(bounds) || bounds.length !== 2 || !bounds.every(Number.isSafeInteger) ||
        bounds[0] < 0 || bounds[0] > bounds[1] || bounds[1] >= count) throw new RangeError("Invalid source event bounds");
    if (kind === "exact" && bounds[0] !== bounds[1]) throw new RangeError("Exact event must use one frame");
    function x(frame) { return left + frame * (right - left) / Math.max(1, count - 1); }
    return { kind: kind, x0: x(bounds[0]), x1: x(bounds[1]),
      bandLeft: Math.max(left, x(bounds[0] - 0.5)), bandRight: Math.min(right, x(bounds[1] + 0.5)),
      dashed: kind === "uncertain", singleFrame: bounds[0] === bounds[1] };
  }

  function pairText(bounds, digits) {
    if (!Array.isArray(bounds) || bounds.length !== 2 || !bounds.every(Number.isFinite)) return "無可用上下界";
    function format(value) { return digits === undefined ? String(value) : value.toFixed(digits); }
    return bounds[0] === bounds[1] ? format(bounds[0]) : format(bounds[0]) + "–" + format(bounds[1]);
  }

  function eventFrameText(event) {
    if (event.marker_kind === "not_observable") return "不可觀測；不推估影格";
    if (!event.frame_bounds) return "不確定；無指定候選範圍";
    return (event.marker_kind === "uncertain" ? "候選 " : "") + pairText(event.frame_bounds) +
      (event.marker_kind === "uncertain" ? "（不確定）" : "");
  }

  function windowText(window) {
    if (!window || !window.total_frames) return "事件範圍未定；不推估角度";
    var values = window.min_deg === null || window.max_deg === null ? "未算出角度" :
      pairText([window.min_deg, window.max_deg], 1) + "°（模型XY）";
    return values + "；計算 " + window.calculated_frames + "/" + window.total_frames +
      "，缺失 " + window.missing_frames + "，退化 " + window.degenerate_frames + "；可用性未知";
  }

  function timingText(interval) {
    if (!interval || interval.status === "unavailable") return "無法界定；" + (interval && interval.reason || "事件未定");
    return (interval.status === "bounded" ? "上下界 " : "") + pairText(interval.seconds_bounds, 4) +
      " 秒；" + pairText(interval.frame_bounds) + " 格";
  }

  var helpers = { eventMarkerGeometry: eventMarkerGeometry, eventFrameText: eventFrameText,
    windowText: windowText, timingText: timingText };
  if (typeof module !== "undefined" && module.exports) module.exports = helpers;
  global.NativeMotionEvents = helpers;
  if (typeof document === "undefined") return;

  function initialize() {
    var dataNode = document.getElementById("motion-data");
    var selector = document.getElementById("clip-select");
    var eventTable = document.getElementById("event-table");
    var timingTable = document.getElementById("event-timing-table");
    var legend = document.getElementById("event-legend");
    if (!dataNode || !selector || !eventTable || !timingTable || !legend) return;
    var clips;
    try {
      clips = JSON.parse(dataNode.textContent).clips;
      if (!Array.isArray(clips) || !clips.length) throw new Error("沒有事件資料");
    } catch (error) {
      eventTable.textContent = "事件資料無法顯示：" + error.message;
      return;
    }

    function element(name, text) {
      var node = document.createElement(name);
      if (text !== undefined) node.textContent = text;
      return node;
    }
    function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
    function table(headers, rows) {
      var result = element("table");
      result.className = "event-table";
      var head = element("thead"), header = element("tr");
      headers.forEach(function (text) {
        var cell = element("th", text);
        cell.setAttribute("scope", "col");
        header.appendChild(cell);
      });
      head.appendChild(header);
      result.appendChild(head);
      var body = element("tbody");
      rows.forEach(function (values) {
        var row = element("tr");
        values.forEach(function (value) { row.appendChild(element("td", value)); });
        body.appendChild(row);
      });
      result.appendChild(body);
      return result;
    }
    function plain(value) {
      if (value === null || value === undefined || value === "") return "未填";
      return typeof value === "object" ? JSON.stringify(value) : String(value);
    }
    function svgNode(name, attributes, text) {
      var node = document.createElementNS("http://www.w3.org/2000/svg", name);
      Object.keys(attributes).forEach(function (key) { node.setAttribute(key, attributes[key]); });
      if (text !== undefined) node.textContent = text;
      return node;
    }

    function decorateChart(svg, clip) {
      if (!svg) return;
      Array.from(svg.querySelectorAll("[data-event-decoration]")).forEach(function (node) { node.remove(); });
      var bands = svgNode("g", { "data-event-decoration": "bands", "pointer-events": "none" });
      var lines = svgNode("g", { "data-event-decoration": "lines", "pointer-events": "none" });
      eventNames.forEach(function (name, index) {
        var marker = eventMarkerGeometry(clip.events[name], clip.frame_count);
        if (marker === null) return;
        var color = colors[index];
        if (marker.kind !== "exact" && !marker.singleFrame) {
          var rect = { x: marker.bandLeft, y: top, width: Math.max(1, marker.bandRight - marker.bandLeft),
            height: bottom - top, fill: color, "fill-opacity": "0.12", stroke: color,
            "stroke-width": "1", "stroke-opacity": "0.8" };
          if (marker.dashed) rect["stroke-dasharray"] = "5 4";
          bands.appendChild(svgNode("rect", rect));
        } else if (marker.kind === "range") {
          bands.appendChild(svgNode("rect", { x: marker.bandLeft, y: top,
            width: Math.max(1, marker.bandRight - marker.bandLeft), height: bottom - top,
            fill: color, "fill-opacity": "0.12", stroke: color }));
        }
        var positions = marker.kind === "exact" || marker.singleFrame ? [marker.x0] : [marker.x0, marker.x1];
        positions.forEach(function (x) {
          var attrs = { x1: x, x2: x, y1: top, y2: bottom, stroke: color, "stroke-width": "1.5" };
          if (marker.dashed) attrs["stroke-dasharray"] = "5 4";
          lines.appendChild(svgNode("line", attrs));
        });
        lines.appendChild(svgNode("text", { x: (marker.x0 + marker.x1) / 2,
          y: top + 13 + index % 2 * 14, fill: color, "text-anchor": "middle",
          "font-size": 12, "font-weight": "bold" }, String(index + 1) + (marker.dashed ? "?" : "")));
      });
      svg.insertBefore(bands, svg.firstChild);
      svg.appendChild(lines);
    }

    function showSelected() {
      var clip = clips[Number(selector.value)];
      if (!clip || !clip.events) return;
      clear(eventTable);
      var rows = eventNames.map(function (name, index) {
        var event = clip.events[name];
        return [String(index + 1) + " " + eventLabels[name], plain(event.status) + " / " + event.marker_kind,
          eventFrameText(event), event.time_bounds_sec ? pairText(event.time_bounds_sec, 4) + " 秒" : "無指定時間範圍",
          windowText(event.angle_windows.throwing_elbow), windowText(event.angle_windows.lead_knee),
          "信心：" + plain(event.confidence) + "；備註：" + plain(event.note)];
      });
      eventTable.appendChild(table([clip.pitch_id + " 人工事件", "原狀態／圖示", "來源影格", "來源時間",
        "投球肘視窗", "前導膝視窗", "人工紀錄"], rows));
      decorateChart(document.getElementById("elbow-chart"), clip);
      decorateChart(document.getElementById("knee-chart"), clip);
    }

    eventNames.forEach(function (name, index) {
      var item = element("span", String(index + 1) + " " + eventLabels[name]);
      item.style.color = colors[index];
      legend.appendChild(item);
    });
    timingTable.appendChild(table(["影片"].concat(timingLabels), clips.map(function (clip) {
      return [clip.pitch_id].concat(timingNames.map(function (name) { return timingText(clip.timing[name]); }));
    })));
    // The base script is loaded first and registers its change handler first.
    // It redraws the original curves; this independent listener then decorates.
    selector.addEventListener("change", showSelected);
    showSelected();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialize, { once: true });
  else initialize();
}(typeof globalThis !== "undefined" ? globalThis : this));
