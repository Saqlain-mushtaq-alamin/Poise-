import asyncio

from app.services.hardware import detect_hardware
from app.services.planner import PLAN_GENERATION_PROMPT
from app.services.provider import ModelProviderRouter


async def main():
    from app.services.tier import ModelPlan
    
    profile = detect_hardware()
    
    # Try to find the qwen model from available ollama models
    target_model = "qwen:8b" # default fallback
    for m in profile.ollama_models:
        if "qwen" in m.lower():
            target_model = m
            break
            
    router = ModelProviderRouter()
    router._model_plan = ModelPlan(llm=target_model, stt="", tts="", embedding="", vlm="")
    router.set_model_override(target_model)
    
    print(f"Testing with model: {target_model}")
    
    prompt = PLAN_GENERATION_PROMPT.format(
        section_budgets='{"behavioral": 15, "technical": 30}',
        difficulty="medium",
        company_format_note="general",
        resume_summary="Software Engineer with 5 years of Python experience.",
        jd_summary="Looking for a Senior Python Developer with FastAPI skills."
    )
    
    print(f"Starting generation with model {router.model_plan.llm}...")
    import time
    start = time.time()
    
    try:
        response = await router.chat(
            messages=[{"role": "user", "content": prompt}],
            model_role="reasoning",
            stream=False,
        )
        print(f"Finished in {time.time() - start:.2f} seconds")
        print("Response length:", len(response))
        print(response[:500])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
