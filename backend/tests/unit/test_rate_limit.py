from unittest.mock import patch

from api.v1.rate_limit import SlidingWindowRateLimiter


class TestSlidingWindowRateLimiter:
    def test_bloquea_al_superar_el_maximo(self):
        limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60)
        assert limiter.allow("1.1.1.1")
        assert limiter.allow("1.1.1.1")
        assert not limiter.allow("1.1.1.1")

    def test_ips_distintas_son_independientes(self):
        limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)
        assert limiter.allow("1.1.1.1")
        assert limiter.allow("2.2.2.2")

    def test_la_ventana_se_libera(self):
        limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)
        with patch("api.v1.rate_limit.time.monotonic", return_value=100.0):
            assert limiter.allow("ip")
            assert not limiter.allow("ip")
        with patch("api.v1.rate_limit.time.monotonic", return_value=161.0):
            assert limiter.allow("ip")
