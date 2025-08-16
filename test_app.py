import pytest
from app import classify_incident

def test_classify_accident():
    description = "A car collision occurred at the highway intersection"
    result = classify_incident(description)
    assert "category" in result
    assert "summary" in result
    assert result["category"] in ["Accident", "Other"]
    assert isinstance(result["summary"], str)

def test_classify_empty():
    description = ""
    result = classify_incident(description)
    assert result["category"] == "Other"
