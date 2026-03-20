import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_investment_module_mount(async_client: AsyncClient):
    response = await async_client.get("/api/investment/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["message"] == "Welcome to the Investment Module"
