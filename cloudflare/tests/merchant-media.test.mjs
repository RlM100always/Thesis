import test from "node:test";
import assert from "node:assert/strict";
import {cleanImage} from "../merchant-routes.js";
test("merchant image URLs require public HTTPS and reject unsafe schemes",()=>{
 assert.equal(cleanImage(""),null);
 assert.equal(cleanImage(null),null);
 assert.equal(cleanImage(" https://images.example.org/shop.webp "),"https://images.example.org/shop.webp");
 for(const bad of [
  "data:image/svg+xml,<svg/>","javascript:alert(1)","http://example.com/product.png",
  "https://localhost/a.jpg","https://local/a.jpg","https://admin:password@example.com/image.jpg",
  "https://127.0.0.1/image.jpg","https://192.168.1.5/p.png","https://[::1]/x.png",
  "https://foo.internal/x.webp","not-a-url","https://example.com/"+ "x".repeat(1000)
 ])assert.throws(()=>cleanImage(bad),undefined,bad);
});
