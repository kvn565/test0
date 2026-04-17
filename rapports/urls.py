# rapports/urls.py
from django.urls import path
from . import views

app_name = 'rapports'

urlpatterns = [
    path('entrees/',       views.rapport_entrees,      name='entrees'),
    path('cout-stock/',    views.rapport_cout_stock,   name='cout_stock'),
    path('sorties/',       views.rapport_sorties,      name='sorties'),
    path('stock-actuel/',  views.rapport_stock_actuel, name='stock_actuel'),
    path('facturation/',   views.rapport_facturation,  name='facturation'),
    # Dans urls.py (app rapports)
    path('stock-actuel/export/excel/', views.export_stock_excel, name='export_stock_excel'),
    path('stock-actuel/export/pdf/',   views.export_stock_pdf,   name='export_stock_pdf'),
    path('entrees/export/excel/', views.export_entrees_excel, name='export_entrees_excel'),
    path('entrees/export/pdf/',   views.export_entrees_pdf,   name='export_entrees_pdf'),
    path('facturation/export/excel/', views.export_facturation_excel, name='export_facturation_excel'),
    path('facturation/export/pdf/',   views.export_facturation_pdf,   name='export_facturation_pdf'),
    path('sorties/export/excel/', views.export_sorties_excel, name='export_sorties_excel'),
    path('sorties/export/pdf/',   views.export_sorties_pdf,   name='export_sorties_pdf'),
    path('cout-stock/export/excel/', views.export_cout_stock_excel, name='export_cout_stock_excel'),
    path('cout-stock/export/pdf/',   views.export_cout_stock_pdf,   name='export_cout_stock_pdf'),
]
