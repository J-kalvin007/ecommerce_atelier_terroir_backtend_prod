"""
Classes de limitation de débit dédiées aux endpoints IA.

Chaque appel à ChatView ou AISearchView déclenche un appel réel à l'API OpenAI
(jusqu'à 1500 tokens). Sans limitation, un simple script en boucle sur un
endpoint public génère une facture non bornée : c'est le risque financier
direct le plus élevé de la plateforme hors paiement.

Trois niveaux de protection sont appliqués, du plus court au plus long :

1. Rafale anonyme   — `*_anon`     : borne l'abus depuis une IP non authentifiée.
2. Rafale utilisateur — `*_user`   : borne l'abus depuis un compte authentifié.
3. Quota mensuel    — `*_monthly`  : plafond de consommation par compte, qui
   empêche un utilisateur légitime (ou un compte compromis) de saturer le budget
   OpenAI en restant sous les seuils horaires.

Les taux eux-mêmes sont définis dans `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`
(config/settings/base.py) et surchargeables par variable d'environnement.

@module apps.chatbot.throttles
"""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class MonthlyQuotaThrottleMixin:
    """
    Étend la syntaxe des taux DRF avec la période `month` (30 jours glissants).

    DRF ne connaît nativement que les périodes `s`, `m`, `h` et `d`. Ce mixin
    ajoute `month` afin de pouvoir exprimer un quota mensuel par utilisateur
    (« 500/month ») sans dupliquer la mécanique de comptage de SimpleRateThrottle.
    """

    def parse_rate(self, rate):
        if rate is None:
            return (None, None)

        num, _, period = rate.partition("/")
        if period.lower() in ("month", "mo"):
            return (int(num), 30 * 24 * 60 * 60)

        return super().parse_rate(rate)


class ChatbotAnonRateThrottle(AnonRateThrottle):
    """Rafale anonyme sur POST /api/v1/chatbot/chat/."""

    scope = "chatbot_anon"


class ChatbotUserRateThrottle(UserRateThrottle):
    """Rafale authentifiée sur POST /api/v1/chatbot/chat/."""

    scope = "chatbot_user"


class ChatbotMonthlyThrottle(MonthlyQuotaThrottleMixin, UserRateThrottle):
    """Quota mensuel de conversations IA par compte authentifié."""

    scope = "chatbot_monthly"


class AISearchAnonRateThrottle(AnonRateThrottle):
    """Rafale anonyme sur POST /api/v1/chatbot/search/."""

    scope = "ai_search_anon"


class AISearchUserRateThrottle(UserRateThrottle):
    """Rafale authentifiée sur POST /api/v1/chatbot/search/."""

    scope = "ai_search_user"


class AISearchMonthlyThrottle(MonthlyQuotaThrottleMixin, UserRateThrottle):
    """Quota mensuel de recherches IA par compte authentifié."""

    scope = "ai_search_monthly"


class RecommendationAnonRateThrottle(AnonRateThrottle):
    """Rafale anonyme sur POST /api/v1/chatbot/recommendations/."""

    scope = "recommendation_anon"


class RecommendationUserRateThrottle(UserRateThrottle):
    """Rafale authentifiée sur POST /api/v1/chatbot/recommendations/."""

    scope = "recommendation_user"
