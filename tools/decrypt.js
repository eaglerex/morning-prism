// 사용법: BRIEFING_PASSWORD=비밀번호 node tools/decrypt.js 파일.enc.json  → 원문을 출력합니다.
const fs=require("fs"),c=require("crypto");
const pw=process.env.BRIEFING_PASSWORD,f=process.argv[2];
if(!pw||!f){console.error("BRIEFING_PASSWORD 와 파일이 필요합니다");process.exit(1)}
const j=JSON.parse(fs.readFileSync(f,"utf8"));
const k=c.pbkdf2Sync(pw,Buffer.from(j.salt,"base64"),j.iter,32,"sha256");
const d=Buffer.from(j.data,"base64");
const dc=c.createDecipheriv("aes-256-gcm",k,Buffer.from(j.iv,"base64"));dc.setAuthTag(d.subarray(d.length-16));
process.stdout.write(Buffer.concat([dc.update(d.subarray(0,d.length-16)),dc.final()]).toString("utf8"));
