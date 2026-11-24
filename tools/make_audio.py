# 브리핑(암호화)을 읽어 남성 아나운서 음성(mp3)으로 만들고, 같은 비밀번호로 암호화해 저장합니다.
# 사용: BRIEFING_PASSWORD=... python tools/make_audio.py <출력폴더> [일수]
import os, sys, json, base64, asyncio, subprocess, shutil, time, tempfile
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from mutagen.mp3 import MP3

OUT = sys.argv[1] if len(sys.argv) > 1 else "_audio"
DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.environ.get("AUDIO_DAYS", "3"))
VOICE = os.environ.get("TTS_VOICE", "ko-KR-InJoonNeural")   # 남성
RATE = os.environ.get("TTS_RATE", "+0%")
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
    for n in range(4):
        try:
            await edge_tts.Communicate(text, VOICE, rate=RATE).save(path)
            if os.path.getsize(path) > 1000:
                return
        except Exception as e:
            last = e
        await asyncio.sleep(3 * (n + 1))
    raise RuntimeError(f"음성 생성 실패: {last}")

async def make_day(d):
    dst = os.path.join(OUT, d)
    if os.path.exists(os.path.join(dst, "manifest.json")):
        print(d, "이미 있음"); return
    b = load_brief(d)
    tmp = tempfile.mkdtemp()
    iters = 300000
    salt = os.urandom(16)
    k = key_for(salt, iters)
    os.makedirs(dst + ".part", exist_ok=True)
    man = {"v": 1, "id": d, "iter": iters, "salt": base64.b64encode(salt).decode(), "voice": VOICE, "tracks": []}
    for ti, tr in enumerate(b["tracks"]):
        segfiles, segs, cur = [], [], 0.0
        for si, sg in enumerate(tr["segments"]):
            p = os.path.join(tmp, f"t{ti}_s{si}.mp3")
            await tts_one(spoken(sg["h"], sg["t"]), p)
            dur = MP3(p).info.length
            segs.append({"start": round(cur, 2), "dur": round(dur, 2)})
            cur += dur; segfiles.append(p)
            print(f"  트랙{ti+1} 구간{si+1} {dur:.0f}초", flush=True)
        lst = os.path.join(tmp, f"t{ti}.txt")
        open(lst, "w").write("".join(f"file '{p}'\n" for p in segfiles))
        full = os.path.join(tmp, f"t{ti}.mp3")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", full], check=True)
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
