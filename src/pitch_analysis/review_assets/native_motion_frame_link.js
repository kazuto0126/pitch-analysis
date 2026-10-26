/* Thin frame-link adapter; all seeking remains in the existing source player. */
(function (global) {
  "use strict";
  function frameFromHash(hash, count) {
    if (!Number.isSafeInteger(count) || count < 1) throw new RangeError("Invalid frame count");
    if (!hash || hash === "#") return null;
    var match = /^#frame=(0|[1-9][0-9]*)(?:&request=([1-9][0-9]*))?$/.exec(hash);
    if (!match || (match[2] && !Number.isSafeInteger(Number(match[2])))) throw new RangeError("Invalid frame link");
    var frame = Number(match[1]);
    if (!Number.isSafeInteger(frame) || frame >= count) throw new RangeError("Frame link is outside this clip");
    return frame;
  }
  if (typeof module !== "undefined" && module.exports) module.exports = {frameFromHash: frameFromHash};
  if (typeof document === "undefined") return;
  function initialize() {
    var node = document.getElementById("motion-data"), input = document.getElementById("frame-input");
    var seek = document.getElementById("seek"), video = document.getElementById("video");
    var status = document.getElementById("frame-link-status");
    if (!node || !input || !seek || !video || !status) return;
    var clips = JSON.parse(node.textContent).clips;
    if (clips.length !== 1) return;
    var pending = null;
    function flush() {
      if (pending === null || seek.disabled || video.readyState < 1) return;
      var frame = pending;
      pending = null;
      input.value = String(frame);
      seek.click();
      status.textContent = "已要求跳至原片第 " + frame + " 格；實際呈現以播放器讀值為準。";
    }
    function request() {
      try {
        pending = frameFromHash(global.location.hash, clips[0].frame_count);
        status.textContent = pending === null ? "可用對照頁的事件界線按鈕定位。" : "等待播放器載入，再定位第 " + pending + " 格。";
        flush();
      } catch (error) {
        pending = null;
        status.textContent = "無法定位：" + error.message;
      }
    }
    global.addEventListener("hashchange", request);
    video.addEventListener("loadedmetadata", flush);
    video.addEventListener("loadeddata", flush);
    video.addEventListener("error", function () {
      pending = null;
      status.textContent = "影片載入失敗，跳格要求已取消；請確認原片／overlay可讀取。";
    });
    request();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialize, {once: true});
  else initialize();
}(typeof window !== "undefined" ? window : globalThis));
