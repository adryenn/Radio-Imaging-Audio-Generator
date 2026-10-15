from django.urls import path
from studio import views
urlpatterns = [path('api/bootstrap', views.bootstrap), path('api/signup', views.signup),
               path('api/signin', views.signin), path('api/signout', views.signout),
               path('api/checkout', views.checkout), path('api/portal', views.portal),
               path('api/audio', views.audio), path('api/stripe/webhook', views.webhook)]
