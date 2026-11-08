import test from "node:test";
import assert from "node:assert/strict";
import { filterAndSortProducts } from "../src/storefrontCatalogue.js";

const products = [
  {id:"p1",name:"Premium Rice",sku:"R-01",category:"Grocery",brand:"Fresh Farm",tags:["Organic"],description:"Long grain",price:850,stock_qty:10},
  {id:"p2",name:"Local Rice",sku:"R-02",category:"Grocery",brand:"Local Foods",tags:["Budget"],description:"Daily rice",price:360,stock_qty:20},
  {id:"p3",name:"Cooking Oil",sku:"O-01",category:"Grocery",brand:"Fresh Farm",tags:["Kitchen"],description:"Soybean oil",price:190,stock_qty:0},
  {id:"p4",name:"Gift Basket",sku:"G-01",category:"Gifts",brand:"Handmade",tags:["Organic"],description:"Seasonal bundle",price:null,quantity:4},
];

test("search matches name, SKU, brand, description and tags",()=>{
  assert.deepEqual(filterAndSortProducts(products,{search:"r-02"}).map(p=>p.id),["p2"]);
  assert.deepEqual(filterAndSortProducts(products,{search:"FRESH FARM"}).map(p=>p.id),["p1","p3"]);
  assert.deepEqual(filterAndSortProducts(products,{search:"soybean"}).map(p=>p.id),["p3"]);
  assert.deepEqual(filterAndSortProducts(products,{search:"organic"}).map(p=>p.id),["p1","p4"]);
});

test("category and tag filters work",()=>{
  assert.deepEqual(filterAndSortProducts(products,{category:"Grocery"}).map(p=>p.id),["p1","p2","p3"]);
  assert.deepEqual(filterAndSortProducts(products,{category:"Organic"}).map(p=>p.id),["p1","p4"]);
});

test("brand filter is case-insensitive and combines with other filters",()=>{
  assert.deepEqual(filterAndSortProducts(products,{brand:"fresh farm"}).map(p=>p.id),["p1","p3"]);
  assert.deepEqual(filterAndSortProducts(products,{brand:"Fresh Farm",stock:"available"}).map(p=>p.id),["p1"]);
});

test("stock filter handles in_stock, quantity and stock_qty shapes",()=>{
  assert.deepEqual(filterAndSortProducts([{id:"a",in_stock:true},{id:"b",in_stock:false}],{stock:"available"}).map(p=>p.id),["a"]);
  assert.deepEqual(filterAndSortProducts(products,{stock:"available"}).map(p=>p.id),["p1","p2","p4"]);
  assert.deepEqual(filterAndSortProducts(products,{stock:"unavailable"}).map(p=>p.id),["p3"]);
});

test("price sorting keeps unpriced products at the end",()=>{
  assert.deepEqual(filterAndSortProducts(products,{sort:"price-low"}).map(p=>p.id),["p3","p2","p1","p4"]);
  assert.deepEqual(filterAndSortProducts(products,{sort:"price-high"}).map(p=>p.id),["p1","p2","p3","p4"]);
});

test("combined filters do not mutate the original product list",()=>{
  const before=products.map(p=>p.id);
  assert.deepEqual(filterAndSortProducts(products,{search:"rice",category:"Grocery",brand:"Local Foods",stock:"available"}).map(p=>p.id),["p2"]);
  assert.deepEqual(products.map(p=>p.id),before);
});
