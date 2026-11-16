"""
Озвучка UpYourEnglish через edge-tts.
Положи этот файл рядом с index.html и запускай:
  python gen_audio.py test   -> 20 фраз всеми голосами в папку audio_test (послушать)
  python gen_audio.py all    -> всё в папку audio (можно прерывать и запускать снова)
"""
import asyncio, hashlib, json, re, sys
from pathlib import Path
import edge_tts

HTML = Path("index.html")
VOICES = {
    "aria": "en-US-AriaNeural",
    "guy": "en-US-GuyNeural",
    "sonia": "en-GB-SoniaNeural",
    "ryan": "en-GB-RyanNeural",
}
WORD_VOICES = ["aria", "guy", "sonia", "ryan"]   # слова
TEXT_VOICES = ["aria", "guy", "sonia", "ryan"]   # примеры, идиомы, времена, фразы
RATE = "-10%"                            # как rate=0.9 в приложении
SAY = {"CD": "C D", "DVD": "D V D", "TV": "T V", "OK": "okay", "a, an": "a"}  # как в приложении


def tid(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def load_texts():
    t = HTML.read_text(encoding="utf-8")
    g = lambda i: json.loads(
        re.search(r'<script id="%s" type="application/json">(.*?)</script>' % i, t, re.S).group(1))
    W, P, I, T = g("words-data"), g("phrases-data"), g("idioms-data"), g("tenses-data")
    words = [w["w"] for w in W]
    ex = ([e[0] for w in W for e in w["ex"]] + [e[0] for i in I for e in i["ex"]]
          + [e[0] for x in T for e in x["ex"]])
    phr = [p["en"] for p in P] + [i["en"] for i in I] + ["Hello! How are you today?"]  # + фраза для кнопки ▶ в меню
    return (list(dict.fromkeys(words)), list(dict.fromkeys(ex)), list(dict.fromkeys(phr)))


done = 0


async def one(sem, text, vname, folder, total):
    global done
    f = folder / vname / (tid(text) + ".mp3")
    if f.exists() and f.stat().st_size > 500:
        done += 1
        return
    f.parent.mkdir(parents=True, exist_ok=True)
    async with sem:
        for k in range(4):
            try:
                tmp = f.with_suffix(".tmp")
                await edge_tts.Communicate(SAY.get(text, text), VOICES[vname], rate=RATE).save(str(tmp))
                tmp.replace(f)
                break
            except Exception:
                await asyncio.sleep(2 * (k + 1))
        else:
            print("FAIL:", vname, text)
    done += 1
    if done % 200 == 0:
        print("%d / %d" % (done, total), flush=True)


async def main(mode):
    words, ex, phr = load_texts()
    if mode == "test":
        folder = Path("audio_test")
        texts = words[:8] + ex[:6] + phr[:6]
        jobs = [(t, v) for t in texts for v in VOICES]
    else:
        folder = Path("audio")
        jobs = [(t, v) for t in words for v in WORD_VOICES]
        jobs += [(t, v) for t in ex + phr for v in TEXT_VOICES]
    sem = asyncio.Semaphore(6)
    await asyncio.gather(*[one(sem, t, v, folder, len(jobs)) for t, v in jobs])
    if mode == "all":
        manifest = {t: tid(t) for t in words + ex + phr}
        (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    print("Готово:", len(jobs), "файлов в", folder)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "test"))
