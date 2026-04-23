# categories/urls.py

from django.urls import path
from . import views

app_name = 'categories'

urlpatterns = [
    path('',                    views.liste_categories,    name='liste'),
    path('creer/',              views.categorie_creer,     name='creer'),
    path('<int:pk>/modifier/',  views.categorie_modifier,  name='modifier'),
    path('<int:pk>/supprimer/', views.categorie_supprimer, name='supprimer'),
]
