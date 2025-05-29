import pytest

def test_api_metrics_summary_has_posts_10d(client):
    resp = client.get("/api/metrics/summary")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "posts_10d" in data
    assert "labels" in data["posts_10d"]
    assert "counts" in data["posts_10d"]
    assert len(data["posts_10d"]["labels"]) == 10
    assert len(data["posts_10d"]["counts"]) == 10

def test_admin_dashboard_has_chart_canvas(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert b'id="chartPosts10d"' in resp.data
