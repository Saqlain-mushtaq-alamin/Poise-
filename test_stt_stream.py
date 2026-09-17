import asyncio
import edge_tts
import io
import av
import numpy as np
import sys
import os
import time

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

async def test():
    test_phrase = (
        "Well, in my opinion, living in a big city offers numerous advantages. "
        "For instance, public transportation is very convenient, and there are many job opportunities. "
        "However, the cost of living can be quite high, which creates pressure for young professionals."
    )
    print("Generating audio...")
    pcm = await gen_audio(test_phrase)
    model = WhisperModel("small.en", device="cpu", compute_type="int8", cpu_threads=8)
    
    chunk_size = 4096 * 2 # ~250ms
    buffer = bytearray()
    
    print("\n--- Testing with Anti-Hallucination & Clean Parameters ---")
    t0 = time.time()
    for i in range(0, len(pcm), chunk_size):
        buffer.extend(pcm[i:i+chunk_size])
        if len(buffer) >= 32000 * 1.5 and (len(buffer) % (32000 * 1.5) < chunk_size):
            audio = np.frombuffer(bytes(buffer), dtype=np.int16).astype(np.float32) / 32768.0
            t_chunk_0 = time.time()
            segs, info = model.transcribe(
                audio,
                language="en",
                beam_size=5,
                temperature=0.0,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                condition_on_previous_text=False,
                repetition_penalty=1.2,
                no_repeat_ngram_size=3,
                compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6,
                hallucination_silence_threshold=1.5,
            )
            raw = list(segs)
            text = " ".join(s.text.strip() for s in raw)
            t_chunk_1 = time.time()
            elapsed = time.time() - t0
            print(f"[{elapsed:5.2f}s | chunk took {(t_chunk_1 - t_chunk_0)*1000:4.0f}ms] '{text}'")

if __name__ == "__main__":
    asyncio.run(test())
