# 브리핑(암호화)을 읽어 남성 아나운서 음성(mp3)으로 만들고, 같은 비밀번호로 암호화해 저장합니다.
# 사용: BRIEFING_PASSWORD=... python tools/make_audio.py <출력폴더> [일수]
import os, sys, json, base64, asyncio, subprocess, shutil, time, tempfile
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from mutagen.mp3 import MP3

OUT = sys.argv[1] if len(sys.argv) > 1 else "_audio"
DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.environ.get("AUDIO_DAYS", "3"))
VOICE = os.environ.get("TTS_VOICE", "ko-KR-HyunsuMultilingualNeural")   # 남성(부드러운 톤)
RATE = os.environ.get("TTS_RATE", "+18%")
PITCH = os.environ.get("TTS_PITCH", "+0Hz")
FALLBACK_VOICE = "ko-KR-InJoonNeural"
PW = os.environ.get("BRIEFING_PASSWORD", "")
FAKE = os.environ.get("FAKE_TTS") == "1"   # 시험용(소리 대신 톤)
if not PW:
    print("BRIEFING_PASSWORD 가 없습니다"); sys.exit(1)

def key_for(salt, iters):
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iters).derive(PW.encode())

def load_brief(d):
    j = json.load(open(f"briefings/{d}.enc.json", encoding="utf8"))
    k = key_for(base64.b64decode(j["salt"]), j["iter"])
    pt = AESGCM(k).decrypt(base64.b64decode(j["iv"]), base64.b64decode(j["data"]), None)
    return json.loads(pt.decode("utf8"))

def spoken(h, t):
    h = (h or "").replace("·", ",").strip()
    return t if h in ("오프닝", "클로징", "") else f"{h}. {t}"

async def tts_one(text, path):
    if FAKE:
        secs = max(1.0, len(text) / 6.0)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=330:duration={secs}",
                        "-ac", "1", "-ar", "24000", "-b:a", "48k", path], check=True)
        return
    import edge_tts
    last = None
    for n in range(5):
        v = VOICE if n < 3 else FALLBACK_VOICE
        try:
            kw = {"rate": RATE}
            if v == VOICE and PITCH != "+0Hz": kw["pitch"] = PITCH
            await asyncio.wait_for(edge_tts.Communicate(text, v, **kw).save(path), 120)
            if os.path.getsize(path) > 1000:
                return
        except Exception as e:
            last = e
        await asyncio.sleep(2)
    raise RuntimeError(f"음성 생성 실패: {last}")

async def make_day(d):
    import hashlib
    dst = os.path.join(OUT, d)
    mf = os.path.join(dst, "manifest.json")
    b = load_brief(d)
    chash = hashlib.sha256(json.dumps(b, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    if os.path.exists(mf):
        old = json.load(open(mf))
        newest = d == json.load(open("briefings/index.json"))["dates"][0]
        same = (old.get("voice"), old.get("rate"), old.get("pitch"), old.get("hash")) == (VOICE, RATE, PITCH, chash)
        if same or (not newest and old.get("hash") == chash):
            print(d, "이미 있음"); return
    tmp = tempfile.mkdtemp()
    iters = 300000
    salt = os.urandom(16)
    k = key_for(salt, iters)
    os.makedirs(dst + ".part", exist_ok=True)
    man = {"v": 1, "id": d, "iter": iters, "salt": base64.b64encode(salt).decode(), "voice": VOICE, "rate": RATE, "pitch": PITCH, "hash": chash, "tracks": []}
    for ti, tr in enumerate(b["tracks"]):
        segfiles, segs, cur = [], [], 0.0
        sem = asyncio.Semaphore(4)  # 4개씩 동시에 만들어 시간을 줄입니다
        async def one(si, sg):
            p = os.path.join(tmp, f"t{ti}_s{si}.mp3")
            async with sem:
                await tts_one(spoken(sg["h"], sg["t"]), p)
            return p
        paths = await asyncio.gather(*[one(si, sg) for si, sg in enumerate(tr["segments"])])
        for si, p in enumerate(paths):
            dur = MP3(p).info.length
            segs.append({"start": round(cur, 2), "dur": round(dur, 2)})
            cur += dur; segfiles.append(p)
            print(f"  트랙{ti+1} 구간{si+1} {dur:.0f}초", flush=True)
        lst = os.path.join(tmp, f"t{ti}.txt")
        open(lst, "w").write("".join(f"file '{p}'\n" for p in segfiles))
        full = os.path.join(tmp, f"t{ti}.mp3")
        if shutil.which("ffmpeg"):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", full], check=True)
        else:  # ffmpeg 가 없으면 mp3 를 이어 붙이기(같은 형식이라 재생에 문제 없음)
            with open(full, "wb") as w:
                for pth in segfiles:
                    w.write(open(pth, "rb").read())
        iv = os.urandom(12)
        enc = AESGCM(k).encrypt(iv, open(full, "rb").read(), None)
        fn = f"t{ti+1}.bin"
        open(os.path.join(dst + ".part", fn), "wb").write(enc)
        man["tracks"].append({"file": fn, "iv": base64.b64encode(iv).decode(), "dur": round(cur, 2), "segs": segs})
    json.dump(man, open(os.path.join(dst + ".part", "manifest.json"), "w"))
    if os.path.exists(dst): shutil.rmtree(dst)
    os.rename(dst + ".part", dst)
    shutil.rmtree(tmp, ignore_errors=True)
    print(d, "완료")

async def main():
    os.makedirs(OUT, exist_ok=True)
    dates = json.load(open("briefings/index.json"))["dates"][:DAYS]
    for d in os.listdir(OUT):
        if d not in dates and not d.endswith(".part"):
            shutil.rmtree(os.path.join(OUT, d), ignore_errors=True)
    for d in dates:
        try:
            await make_day(d)
        except Exception as e:
            print("실패", d, e)
            shutil.rmtree(os.path.join(OUT, d + ".part"), ignore_errors=True)

asyncio.run(main())
