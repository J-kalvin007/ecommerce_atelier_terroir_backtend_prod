from rest_framework.routers import DefaultRouter
from .views import FraisLivraisonViewSet, DeliveryViewSet, LivreurViewSet

app_name = "livraisons"

router = DefaultRouter()
router.register(r"frais", FraisLivraisonViewSet, basename="frais")
router.register(r"suivi", DeliveryViewSet, basename="suivi")
router.register(r"livreurs", LivreurViewSet, basename="livreurs")

urlpatterns = router.urls
