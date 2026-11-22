from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """20 par page par défaut ; `?page_size=` jusqu'à 100 (sélecteurs, dashboard)."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
