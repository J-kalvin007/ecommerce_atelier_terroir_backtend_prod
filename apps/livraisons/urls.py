from rest_framework.routers import DefaultRouter
from .views import FraisLivraisonViewSet, DeliveryViewSet

app_name = "livraisons"

router = DefaultRouter()
router.register(r"frais", FraisLivraisonViewSet, basename="frais")
router.register(r"suivi", DeliveryViewSet, basename="suivi")

urlpatterns = router.urls
