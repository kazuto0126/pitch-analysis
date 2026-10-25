/* Source-frame navigation on saved, event-aligned model-XY curves. */
(function (global) {
  "use strict";
  function clipInfo(clip) {
    var match = typeof clip.fps_fraction === "string" && /^([1-9][0-9]*)(?:\/([1-9][0-9]*))?$/.exec(clip.fps_fraction);
    var n = match && Number(match[1]), d = match && Number(match[2] || 1);
    if (!match || !Number.isSafeInteger(n) || !Number.isSafeInteger(d) ||
        !Number.isSafeInteger(clip.frame_count) || clip.frame_count < 1 ||
        !Number.isSafeInteger(clip.alignment_frame) || clip.alignment_frame < 0 || clip.alignment_frame >= clip.frame_count) {
      throw new RangeError("Invalid aligned source timeline");
    }
    return {n: n, d: d, first: -clip.alignment_frame * d / n,
      last: (clip.frame_count - 1 - clip.alignment_frame) * d / n};
  }
  function relativeTime(clip, frame) {
    var info = clipInfo(clip);
    return (frame - clip.alignment_frame) * info.d / info.n;
  }
  function sourceFrameAt(clip, seconds) {
    var info = clipInfo(clip);
    if (typeof seconds !== "number" || !Number.isFinite(seconds)) throw new RangeError("Relative time must be finite");
    if (seconds < info.first || seconds > info.last) return null;
    var frame = Math.round(seconds * info.n / info.d + clip.alignment_frame);
    return frame === 0 ? 0 : frame;
  }
  function segmentPoints(clip, role) {
    clipInfo(clip);
    if (["throwing_elbow", "lead_knee"].indexOf(role) < 0 || !Array.isArray(clip.rows) || clip.rows.length !== clip.frame_count) {
      throw new RangeError("Invalid aligned curve");
    }
    var segments = [], current = [];
    function flush() { if (current.length) segments.push(current); current = []; }
    clip.rows.forEach(function (row, index) {
      if (row.frame_index !== index) throw new RangeError("Incomplete source frames");
      var angle = row[role + "_model_xy_deg"];
      if (row[role + "_coordinate_status"] !== "calculated_from_model_xy" || typeof angle !== "number" || !Number.isFinite(angle)) flush();
      else current.push([relativeTime(clip, index), angle, index]);
    });
    flush();
    return segments;
  }
  function navigationState() {
    var pending = null;
    function valid(index) { if (!Number.isSafeInteger(index) || index < 0) throw new RangeError("Invalid clip or frame"); }
    return {
      request: function (clipIndex, frame) { valid(clipIndex); valid(frame); pending = {clipIndex: clipIndex, frame: frame}; return Object.assign({}, pending); },
      selected: function (index) { valid(index); if (pending && pending.clipIndex !== index) pending = null; },
      ready: function (index, available) {
        valid(index);
        if (!pending || pending.clipIndex !== index || available !== true) return null;
        var result = pending; pending = null; return result;
      },
      cancel: function () { pending = null; }
    };
  }
  var helpers = {sourceFrameAt: sourceFrameAt, segmentPoints: segmentPoints, navigationState: navigationState};
  if (typeof module !== "undefined" && module.exports) module.exports = helpers;
  global.NativeMotionAlignment = helpers;
  if (typeof document === "undefined") return;

  function initialize() {
    var ids = ["motion-data", "clip-select", "video", "frame-input", "seek", "frame-label", "sync-status", "alignment-clips",
      "alignment-window", "alignment-status", "aligned-elbow-chart", "aligned-knee-chart"];
    var el = {};
    ids.forEach(function (id) { el[id] = document.getElementById(id); });
    if (ids.some(function (id) { return !el[id]; })) return;
    var clips, segments;
    try {
      clips = JSON.parse(el["motion-data"].textContent).clips;
      if (!Array.isArray(clips) || !clips.length) throw new Error("缺少曲線資料");
      segments = clips.map(function (clip) { return {throwing_elbow: segmentPoints(clip, "throwing_elbow"), lead_knee: segmentPoints(clip, "lead_knee")}; });
    } catch (error) { el["alignment-status"].textContent = "曲線無法載入：" + error.message; return; }
    var colors = ["#0072b2", "#d55e00", "#009e73", "#cc79a7", "#82660a"];
    var nav = navigationState(), cursors = [], limits = [-.5, .5];
    var ns = "http://www.w3.org/2000/svg", left = 64, right = 940, top = 20, bottom = 236;
    function node(name, attrs, text) {
      var value = document.createElementNS(ns, name);
      Object.keys(attrs).forEach(function (key) { value.setAttribute(key, attrs[key]); });
      if (text !== undefined) value.textContent = text;
      return value;
    }
    function xForTime(time) { return left + (time-limits[0]) * (right-left) / (limits[1]-limits[0]); }
    function yForAngle(angle) { return bottom - angle * (bottom-top) / 180; }
    function currentIndex() { return Number(el["clip-select"].value); }
    function updateCursor() {
      var clip = clips[currentIndex()];
      var match = /^([0-9]+)\s*\//.exec(el["frame-label"].textContent);
      var frame = match ? Number(match[1]) : null;
      var seconds = frame === null ? null : relativeTime(clip, frame);
      cursors.forEach(function (cursor) {
        var visible = seconds !== null && seconds >= limits[0] && seconds <= limits[1];
        cursor.setAttribute("display", visible ? "inline" : "none");
        if (visible) { cursor.setAttribute("x1", xForTime(seconds)); cursor.setAttribute("x2", xForTime(seconds)); }
      });
      var mode = el["sync-status"].textContent.indexOf("時間估計") >= 0 ? "時間估計原片第 " : "目前呈現原片第 ";
      el["alignment-status"].textContent = clip.pitch_id + (frame === null ? "：等待影片呈現影格，請查看播放器同步狀態。" :
        "：" + mode + frame + " 格；相對落地 " + seconds.toFixed(6) + " 秒（" + (frame-clip.alignment_frame) + " 格）。");
    }
    function draw(svg, role) {
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      var id = "alignment-clip-" + role;
      var defs = node("defs", {}), clipPath = node("clipPath", {id: id});
      clipPath.appendChild(node("rect", {x: left, y: top, width: right-left, height: bottom-top}));
      defs.appendChild(clipPath); svg.appendChild(defs);
      [0,45,90,135,180].forEach(function (angle) {
        var y = yForAngle(angle);
        svg.appendChild(node("line", {x1:left,x2:right,y1:y,y2:y,stroke:"#dde4ec"}));
        svg.appendChild(node("text", {x:left-8,y:y+4,"text-anchor":"end","font-size":12}, angle+"°"));
      });
      for (var tick=0; tick<=4; tick++) {
        var time=limits[0]+tick*(limits[1]-limits[0])/4;
        svg.appendChild(node("text", {x:xForTime(time),y:258,"text-anchor":"middle","font-size":12}, time.toFixed(2)));
      }
      svg.appendChild(node("text", {x:(left+right)/2,y:277,"text-anchor":"middle","font-size":12}, "相對人工落地的秒數"));
      var group = node("g", {"clip-path":"url(#"+id+")"});
      var selected = clips[currentIndex()], release = selected.aligned_events.approximate_release;
      if (release.relative_seconds_bounds !== null) {
        var a=xForTime(release.relative_seconds_bounds[0]), b=xForTime(release.relative_seconds_bounds[1]);
        var color=colors[currentIndex()%colors.length], dashed=release.status === "uncertain" ? "5 4" : "none";
        if (release.marker_kind === "range" || b !== a) group.appendChild(node("rect", {x:a,y:top,width:Math.max(1,b-a),height:bottom-top,fill:color,"fill-opacity":.12}));
        group.appendChild(node("line", {x1:a,x2:a,y1:top,y2:bottom,stroke:color,"stroke-width":1.3,"stroke-dasharray":dashed}));
        if (b !== a) group.appendChild(node("line", {x1:b,x2:b,y1:top,y2:bottom,stroke:color,"stroke-width":1.3,"stroke-dasharray":dashed}));
      }
      segments.forEach(function (curves,index) {
        curves[role].forEach(function (points) {
          var attrs = {"data-clip-index":index,fill:"none",stroke:colors[index%colors.length],"stroke-width":index === currentIndex() ? 2.4 : 1.3};
          if (points.length === 1) {
            attrs.cx=xForTime(points[0][0]); attrs.cy=yForAngle(points[0][1]); attrs.r=3; attrs.fill=attrs.stroke;
            group.appendChild(node("circle",attrs));
          } else {
            attrs.points=points.map(function (p) { return xForTime(p[0])+","+yForAngle(p[1]); }).join(" ");
            attrs["stroke-linejoin"]="round"; attrs["pointer-events"]="stroke";
            group.appendChild(node("polyline",attrs));
          }
        });
      });
      group.appendChild(node("line",{x1:xForTime(0),x2:xForTime(0),y1:top,y2:bottom,stroke:"#29384b","stroke-dasharray":"4 3","pointer-events":"none"}));
      var cursor=node("line",{x1:left,x2:left,y1:top,y2:bottom,stroke:"#141c28","stroke-width":2,display:"none","pointer-events":"none"});
      group.appendChild(cursor); cursors.push(cursor); svg.appendChild(group);
    }
    function redraw() {
      if (el["alignment-window"].value === "full") {
        limits = [Math.min.apply(null,clips.map(function(c){return clipInfo(c).first;})), Math.max.apply(null,clips.map(function(c){return clipInfo(c).last;}))];
        if (limits[0] === limits[1]) limits=[limits[0]-.5,limits[1]+.5];
      } else limits=[-.5,.5];
      cursors=[];
      draw(el["aligned-elbow-chart"],"throwing_elbow"); draw(el["aligned-knee-chart"],"lead_knee"); updateCursor();
    }
    function applyPending() {
      var index=currentIndex(), current=el.video.currentSrc;
      var expected=new URL(clips[index].overlay_url,document.baseURI).href;
      var request=nav.ready(index, !el.seek.disabled && el.video.readyState>=1 && current===expected);
      if (!request) return;
      el["frame-input"].value=String(request.frame); el.seek.click();
    }
    function navigate(index,frame) {
      nav.request(index,frame);
      if (currentIndex() !== index) {
        el["clip-select"].value=String(index); el["clip-select"].dispatchEvent(new Event("change"));
      }
      applyPending();
    }
    function chartClick(event) {
      var svg=event.currentTarget, matrix=svg.getScreenCTM();
      if (!matrix) return;
      var point=svg.createSVGPoint(); point.x=event.clientX; point.y=event.clientY;
      var local=point.matrixTransform(matrix.inverse());
      if(local.x<left||local.x>right||local.y<top||local.y>bottom) return;
      var target=event.target.getAttribute("data-clip-index");
      var index=target===null?currentIndex():Number(target);
      var time=limits[0]+(local.x-left)*(limits[1]-limits[0])/(right-left);
      var frame=sourceFrameAt(clips[index],time);
      if(frame===null){el["alignment-status"].textContent="此時點超出 "+clips[index].pitch_id+" 的原片範圍，請在曲線範圍內點選。";return;}
      navigate(index,frame);
    }
    clips.forEach(function(clip,index){
      var button=document.createElement("button"); button.type="button"; button.textContent=clip.pitch_id+" 落地";
      button.style.color=colors[index%colors.length]; button.addEventListener("click",function(){navigate(index,clip.alignment_frame);});
      el["alignment-clips"].appendChild(button);
    });
    el["clip-select"].addEventListener("change",function(){nav.selected(currentIndex());redraw();});
    el["alignment-window"].addEventListener("change",redraw);
    [el["aligned-elbow-chart"],el["aligned-knee-chart"]].forEach(function(svg){svg.addEventListener("click",chartClick);});
    el.video.addEventListener("loadedmetadata",applyPending);
    el.video.addEventListener("loadeddata",applyPending);
    el.video.addEventListener("error",function(){nav.cancel();});
    var observer = new MutationObserver(updateCursor);
    [el["frame-label"],el["sync-status"]].forEach(function(value){observer.observe(value,{childList:true,characterData:true,subtree:true});});
    redraw();
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded",initialize,{once:true});
  else initialize();
}(typeof globalThis!=="undefined"?globalThis:this));
