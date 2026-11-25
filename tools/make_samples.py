# 목소리 후보를 짧게 들어볼 수 있는 샘플 mp3 를 만듭니다 (공개되어도 무방한 인사말만 사용).
import asyncio, os, sys, edge_tts
OUT = sys.argv[1] if len(sys.argv) > 1 else "_samples"
TEXT = ("좋은 아침입니다. 모닝 프리즘 브리핑을 시작하겠습니다. "
        "오늘은 세계 경제 흐름과 신문 칼럼, 그리고 건축과 예술 이야기를 차분하게 전해 드립니다. "
        "경제협력개발기구는 올해 세계 성장률을 2.9퍼센트로 내다봤습니다. 천천히 들어 주세요. 안전운전하세요.")
H, I = "ko-KR-HyunsuMultilingualNeural", "ko-KR-InJoonNeural"
C = [("G", H, "+18%", "+0Hz"), ("H", H, "+25%", "+0Hz"), ("I", I, "+18%", "+6Hz"),
     ("J", I, "+25%", "+0Hz"), ("K", "ko-KR-BongJinNeural", "+18%", "+0Hz"), ("L", "ko-KR-GookMinNeural", "+18%", "+0Hz")]
async def main():
    os.makedirs(OUT, exist_ok=True)
    for k, v, r, p in C:
        try:
            kw = {"rate": r}
            if p != "+0Hz": kw["pitch"] = p
            await asyncio.wait_for(edge_tts.Communicate(TEXT, v, **kw).save(os.path.join(OUT, k + ".mp3")), 90)
            print("샘플", k, v, r, p)
        except Exception as e:
            print("샘플 실패", k, e)
asyncio.run(main())
