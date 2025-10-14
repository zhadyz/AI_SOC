"""
Metrics - Common Utilities
AI-Augmented SOC

Prometheus metrics collection for all services.
"""

import logging
from typing import Optional
from prometheus_client import Counter, Histogram, Gauge, Info

logger = logging.getLogger(__name__)


class ServiceMetrics:
    """
    Prometheus metrics wrapper for AI services.

    Provides standard metrics:
    - Request counts
    - Latency histograms
    - Error rates
    - Active connections
    """

    def __init__(self, service_name: str):
        """
        Initialize metrics for service.

        Args:
            service_name: Service identifier
        """
        self.service_name = service_name

        # Service info
        self.info = Info(
            f'{service_name}_info',
            f'{service_name} service information'
        )

        # Request counter
        self.requests_total = Counter(
            f'{service_name}_requests_total',
            f'Total {service_name} requests',
            ['method', 'endpoint', 'status']
        )

        # Latency histogram
        self.request_duration = Histogram(
            f'{service_name}_request_duration_seconds',
            f'{service_name} request duration',
            ['method', 'endpoint'],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0]
        )

        # LLM-specific metrics
        self.llm_requests_total = Counter(
            f'{service_name}_llm_requests_total',
            'Total LLM requests',
            ['model', 'status']
        )

        self.llm_tokens_total = Counter(
            f'{service_name}_llm_tokens_total',
            'Total LLM tokens consumed',
            ['model', 'type']  # type: prompt/completion
        )

        self.llm_latency = Histogram(
            f'{service_name}_llm_latency_seconds',
            'LLM inference latency',
            ['model'],
            buckets=[1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0]
        )

        # Active connections
        self.active_requests = Gauge(
            f'{service_name}_active_requests',
            f'Active {service_name} requests'
        )

        # Error counter
        self.errors_total = Counter(
            f'{service_name}_errors_total',
            f'Total {service_name} errors',
            ['error_type']
        )

        logger.info(f"Metrics initialized for {service_name}")

    def record_request(
        self,
        method: str,
        endpoint: str,
        status: str,
        duration: float
    ):
        """
        Record HTTP request metrics.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            status: Response status (success, error, timeout)
            duration: Request duration in seconds
        """
        self.requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=status
        ).inc()

        self.request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)

    def record_llm_request(
        self,
        model: str,
        status: str,
        latency: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0
    ):
        """
        Record LLM request metrics.

        Args:
            model: Model identifier
            status: Request status (success, error, timeout)
            latency: Inference latency in seconds
            prompt_tokens: Input token count
            completion_tokens: Output token count
        """
        self.llm_requests_total.labels(
            model=model,
            status=status
        ).inc()

        self.llm_latency.labels(model=model).observe(latency)

        if prompt_tokens > 0:
            self.llm_tokens_total.labels(
                model=model,
                type='prompt'
            ).inc(prompt_tokens)

        if completion_tokens > 0:
            self.llm_tokens_total.labels(
                model=model,
                type='completion'
            ).inc(completion_tokens)

    def record_error(self, error_type: str):
        """
        Record error occurrence.

        Args:
            error_type: Error category (timeout, validation, llm_failure, etc.)
        """
        self.errors_total.labels(error_type=error_type).inc()

    def set_info(self, version: str, **kwargs):
        """
        Set service metadata.

        Args:
            version: Service version
            **kwargs: Additional metadata
        """
        info_dict = {'version': version, **kwargs}
        self.info.info(info_dict)


# TODO: Week 6 - Add custom business metrics
# class AlertTriageMetrics(ServiceMetrics):
#     """Alert triage specific metrics"""
#     def __init__(self):
#         super().__init__('alert_triage')
#         self.severity_distribution = Counter(
#             'alert_severity_distribution',
#             'Alert severity distribution',
#             ['severity']
#         )
