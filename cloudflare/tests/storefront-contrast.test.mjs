import test from "node:test";
import assert from "node:assert/strict";
import {contrastColor,contrastRatio,readableAccent} from "../../frontend/src/storeContrast.js";

test("background to foreground algorithm meets AA for all marketplace accents",()=>{
 for(const background of ["#ffffff","#f7faf8","#fdf6ed","#faf5ff","#0d1f16","#091710","#13251b"]){
  for(const accent of ["#ffffff","#f9e45c","#edcffa","#00ff00","#000000","#15452c","#087e59","#db2020","#5e95ff"]){
   const adjusted=readableAccent(accent,background);
   assert.ok(contrastRatio(adjusted,background)>=4.5,
    `background=${background},accent=${accent},adjusted=${adjusted} ratio=${contrastRatio(adjusted,background)}`);
   assert.ok(contrastRatio(adjusted,contrastColor(adjusted))>=4.5,
    `foreground contrast for brand ${adjusted}`);
  }
 }
});
test("brand parsing ignores unsafe values without emitting CSS payloads",()=>{
 for(const input of ["red",null,"var(--bad)","#fff","transparent","url(javascript:alert(1))"]){
  assert.match(readableAccent(input),/^#[0-9a-f]{6}$/i);
 }
});
test("recommended accessible text for green and white background",()=>{
 assert.equal(contrastColor("#ffffff"),"#000000");
 assert.equal(contrastColor("#000000"),"#ffffff");
 assert.ok(contrastRatio("#000000","#ffffff")>20);
});
