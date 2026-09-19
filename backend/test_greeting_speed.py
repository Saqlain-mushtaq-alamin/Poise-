import asyncio

from app.services.hardware import detect_hardware
from app.services.ingestion import JobDescription, ResumeData
from app.services.personas import get_persona
from app.services.provider import ModelProviderRouter
from app.services.tier import ModelPlan
from app.services.warmup import WarmUpConductor


async def main():
    profile = detect_hardware()
    target_model = "qwen:8b"
    for m in profile.ollama_models:
        if "qwen" in m.lower():
            target_model = m
            break
            
    router = ModelProviderRouter()
    router._model_plan = ModelPlan(llm=target_model, stt="", tts="", embedding="", vlm="")
    router.set_model_override(target_model)
    
    conductor = WarmUpConductor(router)
    persona = get_persona("professional")
    resume = ResumeData(full_text="Software Engineer")
    jd = JobDescription(title="Senior Developer")
    
    import time
    start = time.time()
    greeting = await conductor.generate_greeting(persona, resume, jd)
    print(f"Greeting in {time.time() - start:.2f}s: {greeting}")

if __name__ == "__main__":
    asyncio.run(main())
