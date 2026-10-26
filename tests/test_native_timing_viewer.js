"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const {frameFromHash} = require("../src/pitch_analysis/review_assets/native_motion_frame_link.js");
const {selectedPair, eventTargets, eventUrl, durationText} = require("../src/pitch_analysis/review_assets/native_timing_viewer.js");

test("duration labels preserve unavailable and exact zero while displaying fractional seconds", () => {
  assert.equal(durationText(null),"未定");
  assert.equal(durationText(["0","0"]),"0.000000 至 0.000000 秒");
  assert.equal(durationText(["1001/7500","1001/7500"]),"0.133467 至 0.133467 秒");
});

test("frame links preserve zero and endpoints, with repeat-request tokens", () => {
  for (const frame of [0, 1, 7]) {
    assert.equal(frameFromHash("#frame=" + frame, 8), frame);
    assert.equal(frameFromHash("#frame=" + frame + "&request=2", 8), frame);
  }
  assert.equal(frameFromHash("", 8), null);
  assert.equal(frameFromHash("#", 8), null);
  for (const hash of ["#frame=-1", "#frame=8", "#frame=1.2", "#frame=01", "#frame=NaN", "#frame=1&request=0", "#frame=1&request=9007199254740992"]) {
    assert.throws(() => frameFromHash(hash, 8), RangeError);
  }
});

test("event navigation never promotes an uncertain single-frame candidate", () => {
  const clip = {frame_count:8, page_url:"b_000.html", events:{
    exact:{status:"annotated",frame_bounds:[0,0]},
    ranged:{status:"annotated",frame_bounds:[2,5]},
    candidate:{status:"uncertain",frame_bounds:[3,3]},
    hidden:{status:"not_observable",frame_bounds:null}
  }};
  assert.deepEqual(eventTargets(clip,"exact"),[{frame:0,label:"已確認格"}]);
  assert.deepEqual(eventTargets(clip,"ranged").map(x=>x.frame),[2,5]);
  assert.deepEqual(eventTargets(clip,"candidate"),[]);
  assert.deepEqual(eventTargets(clip,"hidden"),[]);
  clip.events.bad={status:"annotated",frame_bounds:[0,8]};
  assert.throws(()=>eventTargets(clip,"bad"),RangeError);
  assert.equal(eventUrl(clip,0),"b_000.html#frame=0");
  assert.notEqual(eventUrl(clip,0,1),eventUrl(clip,0,2));
  assert.throws(()=>eventUrl(clip,8),RangeError);
});

test("pair selection retains saved unavailable reasons and rejects ambiguous identities", () => {
  const row={timing_key:"start",a_pitch_id:"a1",b_pitch_id:"b1",status:"unavailable",unavailable_reasons:{b:"Uncertain"}};
  assert.equal(selectedPair({pairs:[row]},"start","a1","b1"),row);
  assert.throws(()=>selectedPair({pairs:[]},"start","a1","b1"),RangeError);
  assert.throws(()=>selectedPair({pairs:[row,row]},"start","a1","b1"),RangeError);
});

function adapter(hash) {
  const listeners={},videoListeners={},clicked=[];
  const status={textContent:""},input={value:""},seek={disabled:true,click(){clicked.push(input.value);}};
  const video={readyState:0,addEventListener(name,fn){videoListeners[name]=fn;}};
  const elements={"motion-data":{textContent:JSON.stringify({clips:[{frame_count:8}]})},
    "frame-input":input,seek,video,"frame-link-status":status};
  const window={location:{hash},addEventListener(name,fn){listeners[name]=fn;}};
  const document={readyState:"complete",getElementById(id){return elements[id];}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,"../src/pitch_analysis/review_assets/native_motion_frame_link.js"),"utf8"),{window,document});
  return {window,video,seek,clicked,status,
    change(value){window.location.hash=value;listeners.hashchange();},
    ready(){video.readyState=1;seek.disabled=false;videoListeners.loadedmetadata();},
    error(){videoListeners.error();}};
}

test("frame adapter waits for metadata, then invokes the unchanged seek control once", () => {
  const x=adapter("#frame=0");
  assert.deepEqual(x.clicked,[]);
  x.ready();
  assert.deepEqual(x.clicked,["0"]);
  x.ready();
  assert.deepEqual(x.clicked,["0"]);
  assert.match(x.status.textContent,/實際呈現/);
});

test("latest pending frame wins and the same frame can be requested again after playback", () => {
  const x=adapter("#frame=1&request=1");
  x.change("#frame=7&request=2");
  x.ready();
  assert.deepEqual(x.clicked,["7"]);
  x.change("#frame=7&request=3");
  assert.deepEqual(x.clicked,["7","7"]);
});

test("invalid hashes and video errors discard pending requests without clamping", () => {
  const invalid=adapter("#frame=2");
  invalid.change("#frame=8");
  invalid.ready();
  assert.deepEqual(invalid.clicked,[]);
  const failed=adapter("#frame=2");
  failed.error();failed.ready();
  assert.deepEqual(failed.clicked,[]);
  assert.match(failed.status.textContent,/取消/);
});
