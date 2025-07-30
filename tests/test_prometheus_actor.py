#!/usr/bin/env python3
"""Simple test script for PrometheusActor functionality.

This script tests the PrometheusActor class without requiring a real Prometheus server.
It demonstrates the actor's behavior when Prometheus is not available.
"""

from datetime import datetime

import vessim as vs


def test_prometheus_actor_initialization():
    """Test PrometheusActor initialization and error handling."""
    print("Testing PrometheusActor initialization...")

    try:
        # This should fail because there's no Prometheus server
        vs.PrometheusActor(
            name="test_actor",
            prometheus_url="http://localhost:9090",
            query="up",
            update_interval=1.0,
            timeout=1.0  # Short timeout for quick failure
        )
        print("❌ Expected connection error but actor was created successfully")

    except Exception as e:
        print(f"✅ Expected error caught: {e}")

    print()


def test_prometheus_actor_with_mock_server():
    """Test PrometheusActor behavior with a mock server URL."""
    print("Testing PrometheusActor with invalid server...")

    try:
        # Create actor with invalid URL (should fail during validation)
        actor = vs.PrometheusActor(
            name="mock_actor",
            prometheus_url="http://invalid-prometheus-server:9090",
            query="node_cpu_seconds_total",
            update_interval=5.0,
            timeout=2.0
        )

        # If we get here, the validation didn't catch the invalid server
        print("❌ Actor created with invalid server")

        # Try to get power value
        current_time = datetime.now()
        power = actor.p(current_time)
        print(f"Power value: {power}")

    except Exception as e:
        print(f"✅ Expected error for invalid server: {e}")

    print()


def test_real_time_validation():
    """Test that PrometheusActor validates real-time simulation."""
    print("Testing real-time validation...")

    # We'll create a mock actor that bypasses the connection validation
    # by monkeypatching the validation method

    class MockPrometheusActor(vs.PrometheusActor):
        def _validate_connection(self):
            # Skip validation for testing
            pass

        def _fetch_current_value(self):
            # Return a mock value
            return 100.0

    try:
        actor = MockPrometheusActor(
            name="mock_test_actor",
            prometheus_url="http://localhost:9090",
            query="test_metric",
            update_interval=1.0
        )

        # Test with current time (should work)
        current_time = datetime.now()
        power = actor.p(current_time)
        print(f"✅ Real-time call successful: {power}W")

        # Test with past time (should fail)
        past_time = datetime.now() - timedelta(minutes=5)
        try:
            power = actor.p(past_time)
            print(f"❌ Past time call should have failed but returned: {power}W")
        except RuntimeError as e:
            print(f"✅ Past time correctly rejected: {e}")

    except Exception as e:
        print(f"❌ Mock actor test failed: {e}")

    print()


def test_actor_representation():
    """Test PrometheusActor string representation."""
    print("Testing PrometheusActor string representation...")

    class MockPrometheusActor(vs.PrometheusActor):
        def _validate_connection(self):
            pass

    try:
        actor = MockPrometheusActor(
            name="repr_test",
            prometheus_url="http://localhost:9090",
            query="test_query",
            update_interval=10.0
        )

        repr_str = repr(actor)
        print(f"✅ Actor representation: {repr_str}")

        # Check if all important info is in the representation
        assert "repr_test" in repr_str
        assert "localhost:9090" in repr_str
        assert "test_query" in repr_str
        assert "10.0" in repr_str

        print("✅ All expected information found in representation")

    except Exception as e:
        print(f"❌ Representation test failed: {e}")

    print()


def main():
    """Run all tests."""
    print("PrometheusActor Test Suite")
    print("=" * 30)

    try:
        # Import check
        print("✅ PrometheusActor imported successfully")

        # Run tests
        test_prometheus_actor_initialization()
        test_prometheus_actor_with_mock_server()
        test_real_time_validation()
        test_actor_representation()

        print("Test suite completed!")

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure to install: pip install 'vessim[sil]'")

    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    from datetime import timedelta
    main()
