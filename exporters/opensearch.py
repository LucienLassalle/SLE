"""
OpenSearch exporter for SLE
Alias for ElasticsearchExporter (same API)
"""

from exporters.elasticsearch import ElasticsearchExporter


class OpenSearchExporter(ElasticsearchExporter):
    """Export logs to OpenSearch (uses same API as ElasticSearch)"""
    
    def get_name(self) -> str:
        """Get exporter name"""
        return "opensearch"
