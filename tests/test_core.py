import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    # Status can be 'ok' or 'degraded' based on infrastructure availability
    assert data["status"] in ["ok", "degraded"]
