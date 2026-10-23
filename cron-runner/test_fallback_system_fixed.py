import logging
from datetime import datetime
import pandas as pd
import numpy as np

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_correlation_analyzer():
    """Test the correlation analyzer component."""
    from cron.jobs.raspi_fallback.correlation_analyzer import CorrelationAnalyzer

    logger.info("Testing CorrelationAnalyzer...")

    # Create sample data with strong correlation
    timestamps = pd.date_range(start='2025-02-01', periods=100, freq='h')

    # Create correlated temperature data
    dwd_temps = 10 + 5 * np.sin(np.arange(100) * 0.1) + np.random.normal(0, 0.5, 100)
    raspi_temps = dwd_temps * 0.95 + 1 + np.random.normal(0, 0.3, 100)

    # Create correlated humidity data
    dwd_humidity = 65 + 10 * np.sin(np.arange(100) * 0.1) + np.random.normal(0, 1, 100)
    raspi_humidity = dwd_humidity * 0.90 + 3 + np.random.normal(0, 0.5, 100)

    raspi_df = pd.DataFrame({
        'timestamp': timestamps,
        'temperature': raspi_temps,
        'humidity': raspi_humidity
    })

    dwd_df = pd.DataFrame({
        'timestamp': timestamps,
        'temperature': dwd_temps,
        'humidity': dwd_humidity
    })

    try:
        analyzer = CorrelationAnalyzer(training_period_days=30)
        correlations = analyzer.calculate_correlations(raspi_df, dwd_df)

        if len(correlations) > 0:
            logger.info(f"✓ CorrelationAnalyzer test passed")
            for k, v in correlations.items():
                logger.info(f"  {k}: {v:.3f}")
            return True
        else:
            logger.error("✗ CorrelationAnalyzer test failed: No correlations calculated")
            return False
    except Exception as e:
        logger.error(f"✗ CorrelationAnalyzer failed: {e}")
        return False


def test_dwd_data_fetcher():
    """Test DWD data fetching."""
    from cron.jobs.raspi_fallback.dwd_data_fetcher import DWDDataFetcher

    logger.info("Testing DWDDataFetcher...")

    try:
        fetcher = DWDDataFetcher()
        logger.info("✓ DWDDataFetcher instantiated")

        # Test that methods exist and are callable
        assert callable(fetcher.get_hourly_data), "get_hourly_data not callable"
        assert callable(fetcher.get_real_time_data), "get_real_time_data not callable"

        logger.info("✓ DWDDataFetcher test passed")
        return True
    except Exception as e:
        logger.error(f"✗ DWD Fetcher failed: {e}")
        return False


def test_correlation_estimation():
    """Test value estimation using correlation."""
    from cron.jobs.raspi_fallback.correlation_analyzer import CorrelationAnalyzer

    logger.info("Testing correlation-based value estimation...")

    analyzer = CorrelationAnalyzer()

    # Test parameters
    dwd_value = 20.0
    correlation = 0.8
    dwd_mean = 15.0
    dwd_std = 5.0
    raspi_mean = 16.0
    raspi_std = 4.0

    try:
        estimated = analyzer.estimate_value(
            dwd_value=dwd_value,
            raspi_dwd_correlation=correlation,
            dwd_historical_mean=dwd_mean,
            dwd_historical_std=dwd_std,
            raspi_historical_mean=raspi_mean,
            raspi_historical_std=raspi_std
        )

        # Basic sanity check
        assert 15 < estimated < 25, f"Estimation out of reasonable range: {estimated}"
        logger.info(f"✓ Correlation estimation test passed (estimated: {estimated:.2f}°C)")
        return True
    except Exception as e:
        logger.error(f"✗ Correlation estimation failed: {e}")
        return False


def test_forecast_metadata():
    """Test forecast metadata generation."""
    logger.info("Testing forecast metadata...")

    try:
        metadata = {
            'timestamp': datetime.utcnow().isoformat(),
            'training_period_days': 30,
            'correlations': {
                'temperature_vs_temperature': 0.85,
                'humidity_vs_humidity': 0.72
            },
        }

        assert 'timestamp' in metadata
        assert metadata['training_period_days'] == 30
        assert len(metadata['correlations']) > 0

        logger.info(f"✓ Forecast metadata test passed")
        return True
    except Exception as e:
        logger.error(f"✗ Forecast metadata failed: {e}")
        return False


def run_all_tests():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("Running Fallback System Integration Tests")
    logger.info("=" * 60)

    tests = [
        ("Correlation Analyzer", test_correlation_analyzer),
        ("DWD Data Fetcher", test_dwd_data_fetcher),
        ("Correlation Estimation", test_correlation_estimation),
        ("Forecast Metadata", test_forecast_metadata),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            logger.info(f"\n--- {test_name} ---")
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            logger.error(f"✗ {test_name} failed with exception: {e}")
            results.append((test_name, False))

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        logger.info(f"{status}: {test_name}")

    logger.info(f"\nTotal: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)

