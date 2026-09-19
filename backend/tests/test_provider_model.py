from app.services.provider import ModelProviderRouter
from app.services.tier import HardwareTier


def test_model_override():
    router = ModelProviderRouter(tier=HardwareTier.LOCAL_FULL)
    assert router.get_model_override() is None
    
    router.set_model_override("llama3.1:8b")
    assert router.get_model_override() == "llama3.1:8b"
    assert router.model_plan.llm == "llama3.1:8b"
    
    # Reset override
    router.set_model_override(None)
    assert router.get_model_override() is None
    assert router.model_plan.llm != "llama3.1:8b"

def test_provider_model_routes(client):
    res = client.get("/provider/model")
    assert res.status_code == 200
    data = res.json()
    assert "selected_model" in data
    assert "available_models" in data
    
    # Test setting model override
    res_put = client.put("/provider/model", json={"model": "qwen3:8b"})
    assert res_put.status_code == 200
    data_put = res_put.json()
    assert data_put["selected_model"] == "qwen3:8b"
    
    # Clear model override
    res_clear = client.put("/provider/model", json={"model": None})
    assert res_clear.status_code == 200
