import asyncio

from app.services.hardware import detect_hardware
from app.services.provider import get_router


async def main():
    router = get_router()
    profile = detect_hardware()
    print("Ollama available:", profile.ollama_available)
    print("Ollama models:", profile.ollama_models)
    print("Current tier:", router.tier)
    print("Current model plan:", router.model_plan)
    
    # Try resolving a model
    model = router._resolve_model("reasoning")
    print("Resolved reasoning model:", model)
    print("Is cloud model:", router._is_cloud_model(model))
    print("Litellm model name:", router._litellm_model_name(model))
    
    try:
        response = await router.chat(
            messages=[{"role": "user", "content": "Respond with the word Hello and nothing else."}],
            model_role="reasoning",
            stream=False,
            response_format={"type": "json_object"}
        )
        print("Chat response:", response)
    except Exception as e:
        print("Chat error:", repr(e))

if __name__ == "__main__":
    asyncio.run(main())
