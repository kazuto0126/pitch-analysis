"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const {frameFromHash} = require("../src/pitch_analysis/review_assets/native_motion_frame_link.js");
const {selectedPair, eventTargets, eventUrl, durationText, profilePairs, profileStageText, profileJointTexts} = require("../src/pitch_analysis/review_assets/native_timing_viewer.js");

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

function profileFixture() {
  const names=["preparation_start","leg_lift","foot_plant","approximate_release","follow_through_end"];
  const clips=["p1","p2","p3"].map((id,index)=>({pitch_id:id,frame_count:8,fps_fraction:index===2?"60000/1001":"30/1",
    page_url:id+".html",video_url:id+".mp4",events:Object.fromEntries(names.map((name,i)=>[name,{status:"annotated",frame_bounds:[[0,0],[1,1],[3,3],[5,5],[7,7]][i]}])),
    timing:{foot_plant_to_release:{status:"exact",seconds_bounds_fraction:["1/15","1/15"],reason:"Known"},
      release_to_follow_through_end:{status:"exact",seconds_bounds_fraction:["1/15","1/15"],reason:"Known"}}}));
  clips[1].events.approximate_release={status:"uncertain",frame_bounds:[5,5]};
  clips[2].events.approximate_release={status:"annotated",frame_bounds:[4,5]};
  const stages=[
    {key:"foot_plant_to_release",label:"落地至出手",start:"foot_plant",end:"approximate_release"},
    {key:"release_to_follow_through_end",label:"出手至收尾",start:"approximate_release",end:"follow_through_end"}
  ].map(stage=>({...stage,timing_envelope_seconds_fraction:["1/30","1/10"],
    timing_available_clip_ids:["p1","p3"],timing_unavailable_clip_ids:["p2"],
    joints:Object.fromEntries(["throwing_elbow","lead_knee"].map(role=>[role,{
      direction_counts:{positive:1,negative:0,zero:0,includes_zero:1,unavailable:1},
      clip_ids_by_direction:{positive:["p1"],negative:[],zero:[],includes_zero:["p3"],unavailable:["p2"]},common_direction:null,
      clip_summaries:clips.map((c,i)=>({pitch_id:c.pitch_id,transition_status:i===1?"unavailable":"descriptive_model_xy_transition",
        transition_reason:i===1?"Manual event uncertain":"Known endpoints",total_pairs:i===1?null:i===2?2:1,
        calculated_pairs:i===1?null:i===2?2:1,missing_endpoint_pairs:i===1?null:0,degenerate_endpoint_pairs:i===1?null:0,
        min_delta_deg:i===1?null:i===2?-.040605879997:2,max_delta_deg:i===1?null:6,
        delta_direction:i===1?"unavailable":i===2?"includes_zero":"positive"}))
    }]))}));
  const pairs=stages.flatMap((stage,index)=>{
    const order=index===0?[["p1","p2"],["p1","p3"],["p2","p3"]]:[["p1","p3"],["p1","p2"],["p2","p3"]];
    return order.map(([a,b])=>{
      const missing=a==="p2"||b==="p2";
      return {timing_key:stage.key,a_pitch_id:a,b_pitch_id:b,status:missing?"unavailable":"descriptive_manual_timing",
        relation:missing?"unavailable":"a_shorter",a_seconds_bounds_fraction:a==="p2"?null:["1/30","1/30"],
        b_seconds_bounds_fraction:b==="p2"?null:["1/15","1/10"],
        delta_seconds_bounds_fraction:missing?null:["-1/15","-1/30"],delta_seconds_bounds:missing?null:[-1/15,-1/30],
        unavailable_reasons:{a:a==="p2"?"Uncertain release":null,b:b==="p2"?"Uncertain release":null}};
    });
  });
  return {mode:"same_pitcher_profile",pitcher_id:"custom_pitcher",stages,pairs,
    cohorts:[{side:"a",pitcher_id:"custom_pitcher",clips},{side:"b",pitcher_id:"custom_pitcher",clips}]};
}

class Element {
  constructor(tag) {this.tagName=tag;this.value="";this.textContent="";this.children=[];this.listeners={};this.attributes={};this.hidden=false;this.disabled=false;}
  appendChild(child) {this.children.push(child);if(this.tagName==="select"&&this.value==="")this.value=child.value;return child;}
  replaceChildren() {this.children=[];if(this.tagName==="select")this.value="";}
  addEventListener(name,fn) {this.listeners[name]=fn;}
  getAttribute(name) {return this.attributes[name]===undefined?null:this.attributes[name];}
  setAttribute(name,value) {this.attributes[name]=value;}
  fire(name) {assert.ok(this.listeners[name],"Expected "+name+" listener");this.listeners[name]();}
}

function parentViewer(data) {
  const elements={"timing-data":{textContent:JSON.stringify(data)}};
  ["timing-select","a-select","b-select","profile-pair-select"].forEach(id=>{
    elements[id]=new Element("select");elements[id].parentElement=new Element("label");
  });
  ["pair-durations","pair-result","pair-reasons","profile-stage-summary","b-panel"].forEach(id=>elements[id]=new Element("p"));
  for(const side of ["a","b"])for(const part of ["heading","fps","raw","events","player","joints"])elements[side+"-"+part]=new Element(part==="player"?"iframe":"div");
  if(data.mode!=="same_pitcher_profile")for(const id of ["profile-pair-select","profile-stage-summary","a-joints","b-joints","b-panel"])delete elements[id];
  const document={readyState:"complete",getElementById(id){return elements[id];},createElement(tag){return new Element(tag);}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,"../src/pitch_analysis/review_assets/native_timing_viewer.js"),"utf8"),{window:{},document});
  return {elements,change(id,value){elements[id].value=value;elements[id].fire("change");},
    buttons(side){return elements[side+"-events"].children.flatMap(line=>line.children);}};
}

test("profile helpers retain canonical pairs, unknowns and tiny negative endpoint classification", () => {
  const data=profileFixture(),before=JSON.stringify(data),stage=data.stages[0];
  assert.equal(profilePairs(data,stage.key).length,3);
  assert.throws(()=>selectedPair(data,stage.key,"p2","p1"),RangeError);
  assert.throws(()=>selectedPair(data,stage.key,"p1","p1"),RangeError);
  assert.match(profileStageText(stage),/已確認球：p1、p3/);
  assert.match(profileStageText(stage),/事件未定球：p2/);
  assert.match(profileStageText(stage),/unknown.*null/);
  assert.match(profileJointTexts(stage,"p3")[0],/-0\.040606.*原分類：含零/);
  assert.match(profileJointTexts(stage,"p2")[0],/未定.*未定／未定.*Manual event uncertain/);
  assert.equal(JSON.stringify(data),before);
});

test("profile pair and stage selection preserve canonical identity and refresh both endpoints", () => {
  const data=profileFixture(),x=parentViewer(data),e=x.elements;
  assert.equal(e["profile-pair-select"].children.length,3);
  assert.equal(e["a-select"].value,"p1");assert.equal(e["b-select"].value,"p2");
  assert.equal(e["a-select"].parentElement.hidden,true);assert.equal(e["b-select"].parentElement.hidden,true);
  assert.match(e["pair-result"].textContent,/事件不足/);
  assert.match(e["b-joints"].children[0].textContent,/Manual event uncertain/);
  x.change("profile-pair-select","1");
  assert.equal(e["a-select"].value,"p1");assert.equal(e["b-select"].value,"p3");
  assert.match(e["pair-result"].textContent,/A時距較短/);
  assert.match(e["b-fps"].textContent,/60000\/1001/);
  assert.equal(e["b-player"].src,"p3.html");
  assert.match(e["b-joints"].children[0].textContent,/原分類：含零/);
  x.change("timing-select","release_to_follow_through_end");
  assert.equal(e["profile-pair-select"].value,"0");
  assert.equal(e["a-select"].value,"p1");assert.equal(e["b-select"].value,"p3");
  assert.deepEqual(x.buttons("b").map(button=>button.textContent),["範圍下界 4 格","範圍上界 5 格","已確認格 7 格"]);
});

test("profile event buttons skip uncertain candidates and repeat exact source-frame requests", () => {
  const x=parentViewer(profileFixture()),e=x.elements;
  assert.deepEqual(x.buttons("b").map(button=>button.textContent),["已確認格 3 格"]);
  const button=x.buttons("a")[0];button.fire("click");const first=e["a-player"].src;
  button.fire("click");
  assert.match(first,/p1\.html#frame=3&request=1$/);
  assert.match(e["a-player"].src,/p1\.html#frame=3&request=2$/);
  assert.equal(e["b-player"].src,"p2.html");
});

test("single-clip profile keeps recorded timing and one player without inventing a self-pair", () => {
  const data=profileFixture(),clip=data.cohorts[0].clips[0];
  data.cohorts=[{side:"a",pitcher_id:data.pitcher_id,clips:[clip]}];data.pairs=[];
  data.stages.forEach(stage=>{
    stage.timing_available_clip_ids=["p1"];stage.timing_unavailable_clip_ids=[];
    for(const joint of Object.values(stage.joints)){
      joint.clip_summaries=joint.clip_summaries.filter(row=>row.pitch_id==="p1");
      joint.clip_ids_by_direction={positive:["p1"],negative:[],zero:[],includes_zero:[],unavailable:[]};joint.common_direction="positive";
    }
  });
  const x=parentViewer(data),e=x.elements;
  assert.equal(e["profile-pair-select"].children.length,0);assert.equal(e["profile-pair-select"].disabled,true);
  assert.equal(e["b-panel"].hidden,true);assert.equal(e["b-player"].src,undefined);
  assert.equal(e["a-player"].src,"p1.html");assert.match(e["pair-result"].textContent,/單球.*沒有跨球比較/);
  assert.match(e["pair-durations"].textContent,/0\.066667/);
  x.change("timing-select","release_to_follow_through_end");
  assert.equal(e["profile-pair-select"].children.length,0);
  assert.deepEqual(x.buttons("a").map(button=>button.textContent),["已確認格 5 格","已確認格 7 格"]);
});

test("default two-pitcher parent retains independent clip selectors and needs no profile DOM", () => {
  const profile=profileFixture(),a=profile.cohorts[0].clips[0],b={...a,pitch_id:"other",page_url:"other.html",video_url:"other.mp4"};
  const pair={...profile.pairs[1],b_pitch_id:"other"};
  const data={stages:[profile.stages[0]],pairs:[pair],cohorts:[{side:"a",pitcher_id:"pitcher_a",clips:[a]},
    {side:"b",pitcher_id:"pitcher_b",clips:[b]}]};
  const x=parentViewer(data),e=x.elements;
  assert.equal(e["a-select"].parentElement.hidden,false);assert.equal(e["b-select"].parentElement.hidden,false);
  assert.equal(e["a-player"].src,"p1.html");assert.equal(e["b-player"].src,"other.html");
  assert.match(e["pair-result"].textContent,/A時距較短/);
  x.change("a-select","p1");assert.equal(e["a-player"].src,"p1.html");
  assert.equal(e["a-heading"].textContent,"A：pitcher_a");assert.equal(e["b-heading"].textContent,"B：pitcher_b");
});
