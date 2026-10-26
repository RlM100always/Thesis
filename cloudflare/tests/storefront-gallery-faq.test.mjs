import test from "node:test";
import assert from "node:assert/strict";
import {normalizeGallery,normalizeFAQ} from "../merchant-routes.js";

test("gallery accepts at most 4 unique public HTTPS images",()=>{
 assert.deepEqual(normalizeGallery(undefined),[]);
 assert.deepEqual(normalizeGallery(["https://example.org/front.jpg","https://cdn.example.org/side.webp"]),[
 "https://example.org/front.jpg","https://cdn.example.org/side.webp"
 ]);
 for(const v of [
 "https://example.org/photo.webp",
 Array.from({length:5},(_,i)=>"https://example.org/"+i+".png"),
 ["https://example.org/a.jpg","https://example.org/a.jpg"],
 ["http://example.org/no.png"],["https://127.0.0.1/private.jpg"],[null]
 ])assert.throws(()=>normalizeGallery(v));
});
test("store FAQ is bounded with truthful author-editable entries",()=>{
 assert.deepEqual(normalizeFAQ(null),[]);
 assert.deepEqual(normalizeFAQ([{question:"Do you deliver?",answer:"Contact our store for current delivery information."}]),[
 {question:"Do you deliver?",answer:"Contact our store for current delivery information."}
 ]);
 for(const v of [
 {question:"A",answer:"B"},
 Array.from({length:7},()=>({question:"Do you deliver?",answer:"Not currently"})),
 [{question:"No",answer:"Ok"}], [{question:"Valid?",answer:"x"}],[{}]
 ])assert.throws(()=>normalizeFAQ(v));
});
