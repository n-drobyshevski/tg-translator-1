import pytest

def test_api_metrics_summary_has_posts_10d_channels(client):
    resp = client.get("/api/metrics/summary")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "posts_10d_channels" in data
    pc = data["posts_10d_channels"]
    assert "labels" in pc and len(pc["labels"]) == 10
    assert "series" in pc and isinstance(pc["series"], list)

def test_admin_dashboard_has_channel_canvas(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert b'id="chartPosts10dChannels"' in resp.data
