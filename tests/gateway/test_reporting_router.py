# tests/gateway/test_reporting_router.py
import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_tax_report_endpoint(client):
    """Test: GET /api/reporting/tax-report returns Schedule D."""
    response = await client.get("/api/reporting/tax-report?year=2026")

    assert response.status_code == 200
    data = response.json()
    assert "short_term_gains" in data
    assert "long_term_gains" in data
    assert "total_gain" in data


@pytest.mark.asyncio
async def test_form13f_endpoint(client):
    """Test: GET /api/reporting/form-13f returns quarterly filing."""
    response = await client.get("/api/reporting/form-13f?quarter=Q1&year=2026")

    assert response.status_code == 200
    data = response.json()
    assert "cik" in data
    assert "period_ended" in data
    assert "positions" in data


@pytest.mark.asyncio
async def test_audit_export_csv(client):
    """Test: GET /api/reporting/audit-export?format=csv exports CSV."""
    response = await client.get("/api/reporting/audit-export?format=csv")

    assert response.status_code == 200
    data = response.json()
    assert data["format"] == "csv"


@pytest.mark.asyncio
async def test_audit_export_pdf(client):
    """Test: GET /api/reporting/audit-export?format=pdf exports PDF."""
    response = await client.get("/api/reporting/audit-export?format=pdf")

    assert response.status_code == 200
    data = response.json()
    assert data["format"] == "pdf"


@pytest.mark.asyncio
async def test_tax_report_with_lifo_method(client):
    """Test: GET /api/reporting/tax-report with LIFO method."""
    response = await client.get("/api/reporting/tax-report?year=2026&tax_lot_method=LIFO")

    assert response.status_code == 200
    data = response.json()
    assert data["tax_lot_method"] == "LIFO"
    assert "total_gain" in data


@pytest.mark.asyncio
async def test_form13f_with_custom_cik(client):
    """Test: GET /api/reporting/form-13f with custom CIK."""
    response = await client.get("/api/reporting/form-13f?quarter=Q2&year=2026&cik=0007654321")

    assert response.status_code == 200
    data = response.json()
    assert data["cik"] == "0007654321"
    assert "period_ended" in data
