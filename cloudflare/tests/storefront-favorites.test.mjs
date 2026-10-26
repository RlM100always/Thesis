import test from "node:test";
import assert from "node:assert/strict";
import {readFavorites,saveFavorites,toggleFavorite} from "../../frontend/src/storefrontFavorites.js";
const mem=new Map();
globalThis.localStorage={
 getItem:key=>mem.get(key)||null,
 setItem:(key,val)=>mem.set(key,val)
};
test("favorites are unique, per-store and survive reloads",()=>{
 assert.deepEqual(readFavorites("products:store-alpha"),[]);
 assert.deepEqual(toggleFavorite("products:store-alpha",[],"p1"),["p1"]);
 assert.deepEqual(toggleFavorite("products:store-alpha",["p1"],"p2"),["p1","p2"]);
 assert.deepEqual(readFavorites("products:store-alpha"),["p1","p2"]);
 assert.deepEqual(readFavorites("products:store-beta"),[]);
 assert.deepEqual(toggleFavorite("products:store-alpha",readFavorites("products:store-alpha"),"p1"),["p2"]);
 assert.deepEqual(saveFavorites("stores",["s1","s1","s2"]),["s1","s2"]);
});
test("invalid or corrupt local storage never breaks storefront",()=>{
 mem.set("bsmart-wishlist-v1:stores","{broken");
 assert.deepEqual(readFavorites("stores"),[]);
 assert.deepEqual(saveFavorites("stores",["good",null,5,"good"]),["good"]);
 delete globalThis.localStorage;
 assert.deepEqual(readFavorites("stores"),[]);
 assert.deepEqual(saveFavorites("stores",["offline"]),["offline"]);
});
