# from django.urls import path
# from .views import home, query_sql

# urlpatterns = [
#     path("", home, name="home"),  # Maps "/" to home view
#     path("query_sql/", query_sql, name="query_sql"),
# ]

from django.urls import path
from .views import query_ai_view, test_view

urlpatterns = [
    path("", query_ai_view, name="query-ai"),
    path("test/", test_view, name="test"),
]
