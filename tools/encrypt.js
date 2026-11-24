// 사용법: BRIEFING_PASSWORD=비밀번호 node tools/encrypt.js 입력.json
// 입력 JSON(브리핑)을 암호화해 briefings/<id>.enc.json 으로 저장하고 briefings/index.json 을 갱신합니다.
const fs=require("fs"),path=require("path"),crypto=require("crypto");
const pw=process.env.BRIEFING_PASSWORD;const inp=process.argv[2];
if(!pw||!inp){console.error("BRIEFING_PASSWORD 환경변수와 입력 파일이 필요합니다");process.exit(1)}
const raw=fs.readFileSync(inp,"utf8");const b=JSON.parse(raw);
if(!b.id||!b.tracks||b.tracks.length!==5){console.error("id 와 5개 트랙이 필요합니다");process.exit(1)}
const ITER=300000,salt=crypto.randomBytes(16),iv=crypto.randomBytes(12);
const key=crypto.pbkdf2Sync(pw,salt,ITER,32,"sha256");
const c=crypto.createCipheriv("aes-256-gcm",key,iv);
const ct=Buffer.concat([c.update(Buffer.from(JSON.stringify(b),"utf8")),c.final(),c.getAuthTag()]);
const dir=path.join(__dirname,"..","briefings");fs.mkdirSync(dir,{recursive:true});
fs.writeFileSync(path.join(dir,b.id+".enc.json"),JSON.stringify({v:1,iter:ITER,salt:salt.toString("base64"),iv:iv.toString("base64"),data:ct.toString("base64")}));
const ip=path.join(dir,"index.json");let idx={dates:[]};try{idx=JSON.parse(fs.readFileSync(ip,"utf8"))}catch(e){}
if(!idx.dates.includes(b.id))idx.dates.push(b.id);idx.dates.sort().reverse();idx.updated=new Date().toISOString();
fs.writeFileSync(ip,JSON.stringify(idx));console.log("저장:",b.id,"(총",idx.dates.length,"일)");
