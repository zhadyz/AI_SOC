"""
OpenSearch Client - Log Summarization Service
AI-Augmented SOC

Handles log retrieval from OpenSearch/Wazuh Indexer.

Author: HOLLOWED_EYES
Mission: Phase 3 AI Service Integration
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.exceptions import OpenSearchException
from config import settings

logger = logging.getLogger(__name__)


class OpenSearchClient:
    """
    Client for querying OpenSearch/Wazuh Indexer.

    Features:
    - Time-range based log queries
    - Log source filtering (Wazuh, Suricata, Zeek)
    - Pagination and batching
    - Error handling and retries
    """

    def __init__(self):
        """Initialize OpenSearch client"""
        self.client = OpenSearch(
            hosts=[settings.opensearch_host],
            http_auth=(settings.opensearch_user, settings.opensearch_password),
            use_ssl=True,
            verify_certs=settings.opensearch_verify_ssl,
            ssl_show_warn=False,
            connection_class=RequestsHttpConnection,
            timeout=30
        )
        logger.info(f"OpenSearch client initialized: {settings.opensearch_host}")

    async def check_health(self) -> bool:
        """
        Check OpenSearch cluster health.

        Returns:
            bool: True if cluster is accessible
        """
        try:
            health = self.client.cluster.health()
            status = health.get('status', 'unknown')
            logger.info(f"OpenSearch cluster status: {status}")
            return status in ['green', 'yellow']
        except Exception as e:
            logger.error(f"OpenSearch health check failed: {e}")
            return False

    def _build_time_range_query(
        self,
        hours: int,
        log_source: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build Elasticsearch query for time range.

        Args:
            hours: Hours to look back
            log_source: Filter by log source (wazuh, suricata, zeek)

        Returns:
            Dict: Elasticsearch query DSL
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        query = {
            "bool": {
                "must": [
                    {
                        "range": {
                            "@timestamp": {
                                "gte": start_time.isoformat(),
                                "lte": end_time.isoformat()
                            }
                        }
                    }
                ],
                "filter": []
            }
        }

        # Add log source filter
        if log_source:
            if log_source == "wazuh":
                query["bool"]["filter"].append({
                    "term": {"agent.type": "wazuh"}
                })
            elif log_source == "suricata":
                query["bool"]["filter"].append({
                    "term": {"agent.type": "suricata"}
                })
            elif log_source == "zeek":
                query["bool"]["filter"].append({
                    "term": {"agent.type": "zeek"}
                })

        return query

    async def fetch_logs(
        self,
        time_range_hours: int = 24,
        log_source: Optional[str] = None,
        max_logs: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Fetch logs from OpenSearch for specified time range.

        Args:
            time_range_hours: Hours to look back
            log_source: Filter by log source
            max_logs: Maximum number of logs to retrieve

        Returns:
            List[Dict]: Retrieved log documents
        """
        try:
            query = self._build_time_range_query(time_range_hours, log_source)

            logger.info(
                f"Fetching logs: time_range={time_range_hours}h, "
                f"source={log_source}, max={max_logs}"
            )

            response = self.client.search(
                index=settings.opensearch_index_pattern,
                body={
                    "query": query,
                    "size": min(max_logs, 10000),  # OpenSearch max
                    "sort": [{"@timestamp": {"order": "desc"}}],
                    "_source": [
                        "@timestamp",
                        "rule.description",
                        "rule.level",
                        "rule.mitre.id",
                        "agent.name",
                        "data.srcip",
                        "data.dstip",
                        "full_log"
                    ]
                }
            )

            hits = response.get('hits', {}).get('hits', [])
            logs = [hit['_source'] for hit in hits]

            logger.info(f"Retrieved {len(logs)} logs from OpenSearch")
            return logs

        except OpenSearchException as e:
            logger.error(f"OpenSearch query failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching logs: {e}")
            return []

    async def get_log_statistics(
        self,
        time_range_hours: int = 24,
        log_source: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated statistics for logs in time range.

        Args:
            time_range_hours: Hours to look back
            log_source: Filter by log source

        Returns:
            Dict: Statistics (total count, severity breakdown, top rules)
        """
        try:
            query = self._build_time_range_query(time_range_hours, log_source)

            response = self.client.search(
                index=settings.opensearch_index_pattern,
                body={
                    "query": query,
                    "size": 0,  # Don't return documents, just aggregations
                    "aggs": {
                        "severity_breakdown": {
                            "terms": {
                                "field": "rule.level",
                                "size": 15
                            }
                        },
                        "top_rules": {
                            "terms": {
                                "field": "rule.description.keyword",
                                "size": 10
                            }
                        },
                        "mitre_techniques": {
                            "terms": {
                                "field": "rule.mitre.id.keyword",
                                "size": 20
                            }
                        }
                    }
                }
            )

            total_count = response.get('hits', {}).get('total', {}).get('value', 0)
            aggregations = response.get('aggregations', {})

            stats = {
                "total_logs": total_count,
                "time_range_hours": time_range_hours,
                "severity_breakdown": {
                    bucket['key']: bucket['doc_count']
                    for bucket in aggregations.get('severity_breakdown', {}).get('buckets', [])
                },
                "top_rules": [
                    {
                        "rule": bucket['key'],
                        "count": bucket['doc_count']
                    }
                    for bucket in aggregations.get('top_rules', {}).get('buckets', [])
                ],
                "mitre_techniques": [
                    bucket['key']
                    for bucket in aggregations.get('mitre_techniques', {}).get('buckets', [])
                ]
            }

            logger.info(f"Statistics: {total_count} logs in last {time_range_hours}h")
            return stats

        except Exception as e:
            logger.error(f"Failed to get log statistics: {e}")
            return {
                "total_logs": 0,
                "time_range_hours": time_range_hours,
                "severity_breakdown": {},
                "top_rules": [],
                "mitre_techniques": []
            }
