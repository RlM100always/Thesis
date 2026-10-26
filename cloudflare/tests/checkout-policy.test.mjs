import test from "node:test";
import assert from "node:assert/strict";
import {realCODReady,normalizeBangladeshPhone,normalizeCODContact} from "../checkout-policy.js";
const ready={id:"merchant-abc",is_demo:0,owner_id:"owner-abc",real_cod_approved:1};
const good={shipping_name:"Customer Example",shipping_phone:"+8801712345678",shipping_address:"Road 1, Rajshahi, Bangladesh",privacy_consent:true,payment_method:"cod"};
test("production defaults fail closed until explicitly enabled and approved",()=>{
 assert.equal(realCODReady(ready,{}),false);
 assert.equal(realCODReady({...ready,real_cod_approved:0},{ENABLE_REAL_COD:"true"}),false);
 assert.equal(realCODReady({...ready,is_demo:1},{ENABLE_REAL_COD:"true"}),false);
 assert.equal(realCODReady({...ready,owner_id:null},{ENABLE_REAL_COD:"true"}),false);
 assert.equal(realCODReady(ready,{ENABLE_REAL_COD:"true"}),true);
});
test("normalize Bangladesh phone numbers",()=>{
 assert.equal(normalizeBangladeshPhone("+88 01712-345678"),"01712345678");
 assert.equal(normalizeBangladeshPhone("01712345678"),"01712345678");
 assert.equal(normalizeBangladeshPhone("001712345678"),null);
 assert.equal(normalizeBangladeshPhone("01712"),null);
});
test("shipping consent and COD are mandatory",()=>{
 assert.deepEqual(normalizeCODContact(good),{name:"Customer Example",phone:"01712345678",address:"Road 1, Rajshahi, Bangladesh"});
 for(const patch of [{privacy_consent:false},{payment_method:"bkash"},{shipping_phone:"invalid"},{shipping_address:"short"},{shipping_name:"X"},{coupon_code:"FREE"},{payment_screenshot:"data:image/jpeg;base64,aaa"},{store_customer_token:"secret"}]){
  assert.throws(()=>normalizeCODContact({...good,...patch}));
 }
});
