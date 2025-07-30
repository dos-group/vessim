#!/usr/bin/env python3
"""Standalone Prometheus integration test script.

This script tests direct integration with your Prometheus server using
the provided credentials and queries the DCGM_FI_DEV_POWER_USAGE metric.
"""

import json
import time
from datetime import datetime
from typing import Dict, Any, List

import requests
from requests.auth import HTTPBasicAuth


class PrometheusClient:
    """Simple Prometheus client for testing."""
    
    def __init__(self, base_url: str, username: str, password: str):
        """Initialize the Prometheus client.
        
        Args:
            base_url: Base URL of the Prometheus server
            username: Username for authentication
            password: Password for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.auth = HTTPBasicAuth(username, password)
        self.session = requests.Session()
        self.session.auth = self.auth
        
    def query(self, query: str, timeout: float = 10.0) -> Dict[str, Any]:
        """Execute a PromQL query.
        
        Args:
            query: PromQL query string
            timeout: Request timeout in seconds
            
        Returns:
            Query result as dictionary
        """
        url = f"{self.base_url}/api/v1/query"
        params = {"query": query}
        
        try:
            response = self.session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error executing query: {e}")
            return {"status": "error", "error": str(e)}
    
    def query_range(self, query: str, start: str, end: str, step: str = "15s") -> Dict[str, Any]:
        """Execute a PromQL range query.
        
        Args:
            query: PromQL query string
            start: Start time (RFC3339 or Unix timestamp)
            end: End time (RFC3339 or Unix timestamp)
            step: Query resolution step
            
        Returns:
            Query result as dictionary
        """
        url = f"{self.base_url}/api/v1/query_range"
        params = {
            "query": query,
            "start": start,
            "end": end,
            "step": step
        }
        
        try:
            response = self.session.get(url, params=params, timeout=15.0)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error executing range query: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_labels(self, metric_name: str) -> List[str]:
        """Get all label names for a metric.
        
        Args:
            metric_name: Name of the metric
            
        Returns:
            List of label names
        """
        url = f"{self.base_url}/api/v1/labels"
        try:
            response = self.session.get(url, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            if data["status"] == "success":
                return data["data"]
            return []
        except requests.RequestException as e:
            print(f"Error getting labels: {e}")
            return []
    
    def test_connection(self) -> bool:
        """Test connection to Prometheus server.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            result = self.query("up")
            return result.get("status") == "success"
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False


def format_prometheus_result(result: Dict[str, Any]) -> None:
    """Format and print Prometheus query result."""
    if result.get("status") != "success":
        print(f"❌ Query failed: {result.get('error', 'Unknown error')}")
        return
    
    data = result.get("data", {})
    result_type = data.get("resultType")
    results = data.get("result", [])
    
    if not results:
        print("📊 No data returned")
        return
    
    print(f"📊 Query successful! Result type: {result_type}")
    print(f"📊 Found {len(results)} series")
    
    for i, series in enumerate(results):
        metric = series.get("metric", {})
        value = series.get("value")
        values = series.get("values")
        
        print(f"\n🔹 Series {i+1}:")
        
        # Print labels
        if metric:
            print("   Labels:")
            for label, label_value in metric.items():
                print(f"     {label}: {label_value}")
        
        # Print instant value
        if value:
            timestamp, val = value
            dt = datetime.fromtimestamp(float(timestamp))
            print(f"   Value: {val} (at {dt.strftime('%Y-%m-%d %H:%M:%S')})")
        
        # Print range values (show first and last few)
        if values:
            print(f"   Range values ({len(values)} points):")
            show_values = values[:3] + (values[-3:] if len(values) > 6 else [])
            for timestamp, val in show_values:
                dt = datetime.fromtimestamp(float(timestamp))
                print(f"     {dt.strftime('%H:%M:%S')}: {val}")
            if len(values) > 6:
                print(f"     ... ({len(values) - 6} more points)")


def main():
    """Main test function."""
    # Your Prometheus configuration
    prometheus_url = "http://185.216.22.195:30826/prometheus"
    username = "admin"
    password = "zponvkk0HC4oi5Kn1bvI"
    
    print("🔧 Prometheus Integration Test")
    print("=" * 50)
    print(f"Server: {prometheus_url}")
    print(f"Username: {username}")
    print(f"Password: {'*' * len(password)}")
    print()
    
    # Initialize client
    client = PrometheusClient(prometheus_url, username, password)
    
    # Test connection
    print("🔍 Testing connection...")
    if not client.test_connection():
        print("❌ Connection failed! Check your credentials and server URL.")
        return
    
    print("✅ Connection successful!")
    print()
    
    # Test your specific metric
    print("📊 Testing DCGM_FI_DEV_POWER_USAGE query...")
    power_result = client.query("DCGM_FI_DEV_POWER_USAGE")
    format_prometheus_result(power_result)
    print()
    
    # Test variations of your metric
    print("📊 Testing metric variations...")
    
    # Sum all power usage
    print("\n🔹 Total power usage across all devices:")
    total_result = client.query("sum(DCGM_FI_DEV_POWER_USAGE)")
    format_prometheus_result(total_result)
    
    # Average power usage
    print("\n🔹 Average power usage:")
    avg_result = client.query("avg(DCGM_FI_DEV_POWER_USAGE)")
    format_prometheus_result(avg_result)
    
    # Rate of change (if it makes sense for power)
    print("\n🔹 Rate of change over 5 minutes:")
    rate_result = client.query("rate(DCGM_FI_DEV_POWER_USAGE[5m])")
    format_prometheus_result(rate_result)
    
    # Test range query (last 10 minutes)
    print("\n📊 Testing range query (last 10 minutes)...")
    end_time = int(time.time())
    start_time = end_time - 600  # 10 minutes ago
    
    range_result = client.query_range(
        "DCGM_FI_DEV_POWER_USAGE",
        start=str(start_time),
        end=str(end_time),
        step="30s"
    )
    format_prometheus_result(range_result)
    
    # Test additional useful queries
    print("\n📊 Additional useful queries...")
    
    # Check what metrics are available
    print("\n🔹 Testing 'up' metric (basic connectivity):")
    up_result = client.query("up")
    format_prometheus_result(up_result)
    
    # Max power usage
    print("\n🔹 Maximum power usage:")
    max_result = client.query("max(DCGM_FI_DEV_POWER_USAGE)")
    format_prometheus_result(max_result)
    
    # Min power usage
    print("\n🔹 Minimum power usage:")
    min_result = client.query("min(DCGM_FI_DEV_POWER_USAGE)")
    format_prometheus_result(min_result)
    
    print("\n✅ Test completed!")
    print("\nNext steps:")
    print("1. If power values look correct, you can use DCGM_FI_DEV_POWER_USAGE in your applications")
    print("2. Consider using sum(), avg(), or specific device filters based on your needs")
    print("3. The PrometheusActor in Vessim can use any of these queries")


if __name__ == "__main__":
    main()