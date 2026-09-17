import asyncio
import edge_tts
import io
import av
import numpy as np
import sys
import os

sys.path.insert(0, os.path.abspath("backend"))
from app.services.stt import WhisperSTT, HardwareTier
from faster_whisper import WhisperModel

async def gen_audio(text):
    communicate = edge_tts.Communicate(text, 'en-US-JennyNeural')
    mp3_data = bytearray()
    async for chunk in communicate.stream():
        if chunk['type'] == 'audio':
            mp3_data.extend(chunk['data'])
    
    container = av.open(io.BytesIO(bytes(mp3_data)))
    resampler = av.AudioResampler(format='s16', layout='mono', rate=16000)
    pcm = bytearray()
    for frame in container.decode(audio=0):
        frame.pts = None
        for resampled in resampler.resample(frame):
            pcm.extend(resampled.to_ndarray().tobytes())
    return bytes(pcm)

async def test_stream():
    test_phrase = (
        "Well, in my opinion, living in a big city offers numerous advantages. "
        "For instance, public transportation is very convenient, and there are many job opportunities. "
        "However, the cost of living can be quite high, which creates pressure for young professionals."
    )
    print("Generating longer speech audio...")
    pcm = await gen_audio(test_phrase)
    print(f"Audio duration: {len(pcm) / 32000:.2f} seconds")
    
    stt = WhisperSTT(tier=HardwareTier.LOCAL_LITE)
    stt._model = WhisperModel("small.en", device="cpu", compute_type="int8", cpu_threads=8)
    stt._loaded_model_name = stt.model_name
    
    async def chunk_generator():
        chunk_size = 4096 * 2
        for i in range(0, len(pcm), chunk_size):
            yield pcm[i:i+chunk_size]
            await asyncio.sleep(0.05)
            
    print("Streaming transcription results:")
    idx = 0
    import time
    t0 = time.time()
    async for segment in stt.transcribe_stream(chunk_generator(), buffer_seconds=1.5, sample_rate=16000):
        idx += 1
        elapsed = time.time() - t0
        print(f"[{elapsed:.2f}s] #{idx} partial={segment.is_partial}: '{segment.text}'")

if __name__ == "__main__":
    asyncio.run(test_stream())
