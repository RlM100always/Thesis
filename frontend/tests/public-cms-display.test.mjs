import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {normalizePublicCopy,normalizePublicContentTree} from "../src/publicCopy.js";
import {contrastRatio} from "../src/storeContrast.js";
const read=file=>readFileSync(new URL("../src/"+file,import.meta.url),"utf8");

test("stale admin CMS content receives reviewed copy, but new custom values are preserved",()=>{
 assert.equal(normalizePublicCopy("Production capability ও rollout status স্বচ্ছভাবে প্রকাশ করা হয়.","footer.rollout_note"),"কোন সুবিধা চালু আছে আর কোনটি পরীক্ষামূলক, তা স্পষ্টভাবে জানানো হয়।");
 assert.equal(normalizePublicCopy("এক software, বাস্তব ব্যবসার বহু রূপ","real_work_section.title"),"একটি সফটওয়্যার, বিভিন্ন ধরনের ব্যবসার প্রয়োজন");
 assert.equal(normalizePublicCopy("নতুন দোকান — দারুণ পণ্য!","hero.title"),"নতুন দোকান — দারুণ পণ্য!");
 assert.equal(normalizePublicCopy(" ","hero.title","আমাদের দোকানে স্বাগতম"),"আমাদের দোকানে স্বাগতম");
 assert.equal(normalizePublicCopy(undefined,"hero.title","নতুন শিরোনাম"),"নতুন শিরোনাম");
 assert.equal(normalizePublicCopy("https://example.com/stock","story.image_src"),"https://example.com/stock");
});
test("nested CMS overrides normalize only editorial text; keep ids, URLs, and icons intact",()=>{
 const original={
  hero:{title:"এক software, বাস্তব ব্যবসার বহু রূপ",src:"https://example.com/stock"},
  items:[{id:"owner account",icon:"dashboard",title:"Built for Bangladesh",text:"বিক্রি, stock, inventory ও হিসাব"},{id:"abc",title:"নিজস্ব লেখা"}]
 };
 const result=normalizePublicContentTree(original,"homepage");
 assert.equal(result.hero.title,"একটি সফটওয়্যার, বিভিন্ন ধরনের ব্যবসার প্রয়োজন");
 assert.equal(result.hero.src,"https://example.com/stock");
 assert.equal(result.items[0].id,"owner account");
 assert.equal(result.items[0].icon,"dashboard");
 assert.equal(result.items[0].title,"বাংলাদেশের ব্যবসার জন্য");
 assert.equal(result.items[0].text,"বিক্রি, মজুত, মজুত ও হিসাব");
 assert.equal(result.items[1].title,"নিজস্ব লেখা");
});
test("primary CTA buttons have >=4.5:1 contrast in light AND dark mode",()=>{
 for(const color of ["#075b3d","#087046"])
  assert.ok(contrastRatio(color,"#ffffff")>=4.5, `CTA background ${color} contrast ${contrastRatio(color,"#ffffff")}`);
 assert.ok(contrastRatio("#15c27a","#ffffff")<4.5,"captures the old light-on-light dark-mode regression");
 const css=read("index.css");
 assert.match(css,/--public-cta-from:\s*#075b3d/);
 assert.match(css,/--public-cta-to:\s*#087046/);
 assert.match(css,/background: linear-gradient\(135deg, var\(--public-cta-from\), var\(--public-cta-to\)\)/);
 assert.match(css,/\.public-site \.before-after-cell\.after\{background:var\(--pub-after-bg\);color:var\(--pub-after-color\)\}/);
});
test("public React route consumes normalized admin content, not raw stale overrides",()=>{
 const code=read("pages/PublicSite.jsx");
 assert.match(code,/normalizePublicCopy\(content\[key\], key, fallback\)/);
 assert.match(code,/normalizePublicContentTree\(parsed, key\)/);
 assert.match(code,/সিস্টেমের অবস্থা/);
});
