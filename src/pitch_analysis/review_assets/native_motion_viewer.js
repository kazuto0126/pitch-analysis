/* Saved overlay / source-frame curve review. No prediction or annotation writes. */
(function (global) {
  "use strict";

  function fractionalFps(value) {
    if (typeof value === "number" && Number.isFinite(value) && value > 0) return value;
    if (typeof value !== "string" || !/^[1-9][0-9]*(?:\/[1-9][0-9]*)?$/.test(value)) {
      throw new RangeError("FPS must be a positive fractional frame rate");
    }
    var parts = value.split("/");
    var fps = Number(parts[0]) / (parts.length === 2 ? Number(parts[1]) : 1);
    if (!Number.isFinite(fps) || fps <= 0) throw new RangeError("Invalid fractional FPS");
    return fps;
  }

  function frameCount(value) {
    if (!Number.isSafeInteger(value) || value < 1) throw new RangeError("Frame count must be positive");
    return value;
  }

  function clampFrame(value, count) {
    frameCount(count);
    if (typeof value !== "number" || !Number.isFinite(value)) throw new RangeError("Invalid frame index");
    return Math.max(0, Math.min(count - 1, Math.round(value)));
  }

  function frameIndexForMediaTime(mediaTime, fpsFraction, count, estimated) {
    var fps = fractionalFps(fpsFraction);
    frameCount(count);
    if (typeof mediaTime !== "number" || !Number.isFinite(mediaTime)) {
      throw new RangeError("Media time must be finite");
    }
    // A presented frame's PTS identifies its frame. currentTime is instead an
    // estimated position inside a frame interval, and must use floor.
    var frame = estimated ? Math.floor(mediaTime * fps) : Math.round(mediaTime * fps);
    return Math.max(0, Math.min(count - 1, frame));
  }

  function seekTimeForFrame(frame, fpsFraction, count) {
    return (clampFrame(frame, count) + 0.25) / fractionalFps(fpsFraction);
  }

  var helpers = {
    frameIndexForMediaTime: frameIndexForMediaTime,
    seekTimeForFrame: seekTimeForFrame
  };
  if (typeof module !== "undefined" && module.exports) module.exports = helpers;
  global.NativeMotionViewer = helpers;
  if (typeof document === "undefined") return;

  function initialize() {
    var dataNode = document.getElementById("motion-data");
    if (!dataNode) return;
    var ids = ["clip-select", "video", "play", "previous", "next", "frame-slider", "frame-input",
      "seek", "playback-rate", "frame-label", "time-label", "elbow-label", "knee-label", "sync-status",
      "elbow-chart", "knee-chart"];
    var elements = {};
    ids.forEach(function (id) { elements[id] = document.getElementById(id); });
    if (ids.some(function (id) { return !elements[id]; })) return;
    var video = elements.video;
    var clips;
    try {
      clips = JSON.parse(dataNode.textContent).clips;
      if (!Array.isArray(clips) || !clips.length) throw new Error("沒有可檢視的影片");
      clips.forEach(function (item) {
        frameCount(item.frame_count);
        fractionalFps(item.fps_fraction);
        if (!Array.isArray(item.rows) || item.rows.length !== item.frame_count ||
            item.rows.some(function (row, index) { return row.frame_index !== index; })) {
          throw new Error("曲線資料缺少完整的 0 起算影格序列");
        }
        if (typeof item.overlay_url !== "string" || !item.overlay_url) throw new Error("缺少 overlay 路徑");
      });
    } catch (error) {
      elements["sync-status"].textContent = "資料無法載入：" + error.message;
      return;
    }

    var exactPresentation = typeof video.requestVideoFrameCallback === "function";
    var state = {
      clip: null, actualFrame: null, mediaTime: null, requestedFrame: null,
      callbackId: null, animationId: null, generation: 0, charts: {}, error: "", ready: false
    };
    var svgNamespace = "http://www.w3.org/2000/svg";
    var plot = { left: 64, right: 940, top: 20, bottom: 216 };

    function svgNode(name, attrs, text) {
      var node = document.createElementNS(svgNamespace, name);
      Object.keys(attrs || {}).forEach(function (key) { node.setAttribute(key, attrs[key]); });
      if (text !== undefined) node.textContent = text;
      return node;
    }

    function xForFrame(frame) {
      return plot.left + frame * (plot.right - plot.left) / Math.max(1, state.clip.frame_count - 1);
    }

    function yForAngle(angle) {
      return plot.bottom - angle * (plot.bottom - plot.top) / 180;
    }

    function angleAt(frame, role) {
      var row = state.clip.rows[frame];
      var angle = row[role + "_model_xy_deg"];
      return row[role + "_coordinate_status"] === "calculated_from_model_xy" &&
        typeof angle === "number" && Number.isFinite(angle) ? angle : null;
    }

    function drawChart(svg, role, color) {
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      svg.setAttribute("viewBox", "0 0 960 250");
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", (role === "throwing_elbow" ? "投球肘" : "前導膝") +
        "模型二維投影角度；點選以跳至來源影格");
      [0, 45, 90, 135, 180].forEach(function (angle) {
        var y = yForAngle(angle);
        svg.appendChild(svgNode("line", { x1: plot.left, x2: plot.right, y1: y, y2: y,
          stroke: "#8894a8", "stroke-opacity": "0.25", "stroke-width": 1 }));
        svg.appendChild(svgNode("text", { x: plot.left - 9, y: y + 4, "text-anchor": "end",
          "font-size": 12, fill: "currentColor" }, angle + "°"));
      });
      var tickFrames = [0, Math.round((state.clip.frame_count - 1) / 2), state.clip.frame_count - 1];
      tickFrames.filter(function (frame, index) { return tickFrames.indexOf(frame) === index; })
        .forEach(function (frame) {
          svg.appendChild(svgNode("text", { x: xForFrame(frame), y: 235, "text-anchor": "middle",
            "font-size": 12, fill: "currentColor" }, String(frame)));
        });
      svg.appendChild(svgNode("text", { x: (plot.left + plot.right) / 2, y: 249,
        "text-anchor": "middle", "font-size": 11, fill: "currentColor" }, "影格（0 起算）"));

      var segment = [];
      function appendSegment() {
        if (!segment.length) return;
        if (segment.length === 1) {
          svg.appendChild(svgNode("circle", { cx: segment[0][0], cy: segment[0][1], r: 2.2, fill: color }));
        } else {
          svg.appendChild(svgNode("polyline", { points: segment.map(function (point) { return point.join(","); }).join(" "),
            fill: "none", stroke: color, "stroke-width": 2, "stroke-linejoin": "round" }));
        }
        segment = [];
      }
      state.clip.rows.forEach(function (row, frame) {
        var angle = angleAt(frame, role);
        if (angle === null) appendSegment();
        else segment.push([xForFrame(frame), yForAngle(angle)]);
      });
      appendSegment();
      var cursor = svgNode("line", { x1: plot.left, x2: plot.left, y1: plot.top, y2: plot.bottom,
        stroke: "currentColor", "stroke-width": 1.5, "stroke-dasharray": "4 3", display: "none" });
      var point = svgNode("circle", { cx: plot.left, cy: plot.bottom, r: 4.5, fill: color,
        stroke: "currentColor", "stroke-width": 1, display: "none" });
      svg.appendChild(cursor);
      svg.appendChild(point);
      state.charts[role] = { cursor: cursor, point: point };
    }

    function angleLabel(row, role) {
      if (!row) return "尚未呈現影格";
      var angle = angleAt(row.frame_index, role);
      if (angle !== null) return angle.toFixed(1) + "°（模型 2D；逐點可靠性未知）";
      return row[role + "_coordinate_status"] === "degenerate_geometry" ?
        "無角度：幾何退化" : "無角度：座標缺失";
    }

    function render() {
      if (!state.clip) return;
      var actual = state.actualFrame;
      var row = actual === null ? null : state.clip.rows[actual];
      var controlFrame = state.requestedFrame !== null ? state.requestedFrame : actual === null ? 0 : actual;
      elements["frame-slider"].value = String(controlFrame);
      if (document.activeElement !== elements["frame-input"]) elements["frame-input"].value = String(controlFrame);
      elements["frame-label"].textContent = actual === null ? "尚未呈現影格" :
        String(actual) + " / " + String(state.clip.frame_count - 1) + "（0 起算）";
      elements["time-label"].textContent = row ? row.timestamp_sec.toFixed(6) + " 秒（來源時間）" : "—";
      elements["elbow-label"].textContent = "投球肘：" + angleLabel(row, "throwing_elbow");
      elements["knee-label"].textContent = "前導膝：" + angleLabel(row, "lead_knee");
      elements.play.textContent = video.paused ? "播放" : "暫停";
      var mode = exactPresentation ? "已呈現影格（影片回呼）" : "時間估計（currentTime；非實際呈現回報）";
      if (state.requestedFrame !== null) {
        mode += "；要求 " + state.requestedFrame + "，目前 " + (actual === null ? "尚未呈現" : actual) + "，等待同步";
      } else if (actual !== null) mode += "；目前 " + actual;
      if (state.error) mode += "；" + state.error;
      elements["sync-status"].textContent = mode;
      Object.keys(state.charts).forEach(function (role) {
        var chart = state.charts[role];
        chart.cursor.setAttribute("display", actual === null ? "none" : "inline");
        if (actual === null) {
          chart.point.setAttribute("display", "none");
          return;
        }
        var x = xForFrame(actual);
        chart.cursor.setAttribute("x1", x);
        chart.cursor.setAttribute("x2", x);
        var angle = angleAt(actual, role);
        chart.point.setAttribute("display", angle === null ? "none" : "inline");
        if (angle !== null) {
          chart.point.setAttribute("cx", x);
          chart.point.setAttribute("cy", yForAngle(angle));
        }
      });
    }

    function presented(mediaTime, estimated) {
      if (!state.clip || typeof mediaTime !== "number" || !Number.isFinite(mediaTime)) return;
      state.actualFrame = frameIndexForMediaTime(mediaTime, state.clip.fps_fraction, state.clip.frame_count, estimated);
      state.mediaTime = mediaTime;
      if (state.requestedFrame === state.actualFrame) state.requestedFrame = null;
      render();
    }

    function observePresentedFrames(generation) {
      state.callbackId = video.requestVideoFrameCallback(function (now, metadata) {
        if (generation !== state.generation) return;
        state.callbackId = null;
        presented(metadata.mediaTime, false);
        observePresentedFrames(generation);
      });
    }

    function ensurePresentationObserver() {
      if (exactPresentation && state.callbackId === null && state.ready) {
        observePresentedFrames(state.generation);
      }
    }

    function setControlsEnabled(enabled) {
      state.ready = enabled;
      ["play", "previous", "next", "frame-slider", "frame-input", "seek"].forEach(function (id) {
        elements[id].disabled = !enabled;
      });
      // A failed clip must never prevent choosing a different source.
      elements["clip-select"].disabled = false;
    }

    function applyPlaybackRate() {
      var rate = Number(elements["playback-rate"].value);
      if (Number.isFinite(rate) && rate > 0) video.playbackRate = rate;
    }

    function estimatedFrame() {
      if (!exactPresentation && state.clip && video.readyState >= 2) presented(video.currentTime, true);
    }

    function estimateWhilePlaying(generation) {
      if (generation !== state.generation || video.paused || video.ended) return;
      estimatedFrame();
      state.animationId = global.requestAnimationFrame(function () { estimateWhilePlaying(generation); });
    }

    function performSeek() {
      if (!state.ready || state.requestedFrame === null || video.readyState < 1) return;
      try {
        video.currentTime = seekTimeForFrame(state.requestedFrame, state.clip.fps_fraction, state.clip.frame_count);
      } catch (error) {
        state.error = "跳格尚未完成：" + error.message;
        render();
      }
    }

    function requestFrame(target) {
      if (!state.clip || !state.ready) return;
      target = clampFrame(target, state.clip.frame_count);
      video.pause();
      state.error = "";
      if (state.actualFrame === target && !video.seeking) {
        state.requestedFrame = null;
        render();
        return;
      }
      state.requestedFrame = target;
      render();
      performSeek();
    }

    function step(delta) {
      if (!state.clip || !state.ready) return;
      var base = state.requestedFrame !== null ? state.requestedFrame :
        state.actualFrame !== null ? state.actualFrame : 0;
      requestFrame(base + delta);
    }

    function chartClick(event) {
      if (!state.clip || !state.ready) return;
      var svg = event.currentTarget;
      var matrix = svg.getScreenCTM();
      if (!matrix) return;
      var point = svg.createSVGPoint();
      point.x = event.clientX;
      point.y = event.clientY;
      var local = point.matrixTransform(matrix.inverse());
      if (local.x < plot.left || local.x > plot.right || local.y < plot.top || local.y > plot.bottom) return;
      requestFrame((local.x - plot.left) * (state.clip.frame_count - 1) / (plot.right - plot.left));
    }

    function chooseClip(index) {
      setControlsEnabled(false);
      video.pause();
      state.generation += 1;
      if (state.callbackId !== null && typeof video.cancelVideoFrameCallback === "function") {
        video.cancelVideoFrameCallback(state.callbackId);
      }
      if (state.animationId !== null && typeof global.cancelAnimationFrame === "function") {
        global.cancelAnimationFrame(state.animationId);
      }
      state.clip = clips[index];
      state.actualFrame = null;
      state.mediaTime = null;
      state.requestedFrame = 0;
      state.callbackId = null;
      state.animationId = null;
      state.error = "";
      elements["frame-slider"].min = "0";
      elements["frame-slider"].max = String(state.clip.frame_count - 1);
      elements["frame-slider"].step = "1";
      elements["frame-input"].min = "0";
      elements["frame-input"].max = String(state.clip.frame_count - 1);
      elements["frame-input"].step = "1";
      elements["frame-input"].value = "0";
      drawChart(elements["elbow-chart"], "throwing_elbow", "#1479b8");
      drawChart(elements["knee-chart"], "lead_knee", "#cc6c18");
      video.src = state.clip.overlay_url;
      video.load();
      applyPlaybackRate();
      render();
    }

    while (elements["clip-select"].firstChild) elements["clip-select"].removeChild(elements["clip-select"].firstChild);
    clips.forEach(function (clip, index) {
      var option = document.createElement("option");
      option.value = String(index);
      option.textContent = clip.pitch_id;
      elements["clip-select"].appendChild(option);
    });
    elements["clip-select"].addEventListener("change", function () { chooseClip(Number(this.value)); });
    elements.previous.addEventListener("click", function () { step(-1); });
    elements.next.addEventListener("click", function () { step(1); });
    elements["frame-slider"].addEventListener("input", function () { requestFrame(Number(this.value)); });
    elements.seek.addEventListener("click", function () {
      var text = elements["frame-input"].value.trim();
      if (!/^\d+$/.test(text) || !Number.isSafeInteger(Number(text))) {
        state.error = "請輸入 0 起算的整數影格，再按前往";
        render();
        return;
      }
      requestFrame(Number(text));
    });
    elements.play.addEventListener("click", function () {
      if (!state.ready) return;
      if (!video.paused) video.pause();
      else {
        state.error = "";
        var promise = video.play();
        if (promise && typeof promise.catch === "function") promise.catch(function (error) {
          state.error = "無法播放：" + error.message;
          render();
        });
      }
    });
    elements["playback-rate"].addEventListener("change", applyPlaybackRate);
    [elements["elbow-chart"], elements["knee-chart"]].forEach(function (svg) {
      svg.addEventListener("click", chartClick);
    });
    document.addEventListener("keydown", function (event) {
      if (!state.ready) return;
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      var target = event.target;
      if (target && (target.isContentEditable || /^(INPUT|SELECT|TEXTAREA)$/.test(target.tagName))) return;
      if (event.ctrlKey || event.altKey || event.metaKey) return;
      event.preventDefault();
      step(event.key === "ArrowLeft" ? -1 : 1);
    });
    video.addEventListener("loadedmetadata", function () {
      setControlsEnabled(true);
      applyPlaybackRate();
      // Register against the newly loaded source, before its initial seek. A
      // callback registered before src/load can belong to the discarded source.
      ensurePresentationObserver();
      performSeek();
    });
    video.addEventListener("loadeddata", function () {
      ensurePresentationObserver();
      estimatedFrame();
    });
    video.addEventListener("timeupdate", estimatedFrame);
    video.addEventListener("seeked", estimatedFrame);
    video.addEventListener("play", function () {
      render();
      if (!exactPresentation && typeof global.requestAnimationFrame === "function") {
        if (state.animationId !== null) global.cancelAnimationFrame(state.animationId);
        estimateWhilePlaying(state.generation);
      }
    });
    video.addEventListener("pause", function () { estimatedFrame(); render(); });
    video.addEventListener("ended", function () { estimatedFrame(); render(); });
    video.addEventListener("error", function () {
      setControlsEnabled(false);
      video.pause();
      state.generation += 1;
      if (state.callbackId !== null && typeof video.cancelVideoFrameCallback === "function") {
        video.cancelVideoFrameCallback(state.callbackId);
      }
      state.callbackId = null;
      state.error = "影片無法載入；請確認 overlay 檔案存在且瀏覽器支援 MP4";
      render();
    });
    chooseClip(0);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialize, { once: true });
  else initialize();
}(typeof globalThis !== "undefined" ? globalThis : this));
