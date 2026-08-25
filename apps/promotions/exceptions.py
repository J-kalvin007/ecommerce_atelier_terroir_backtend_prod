


"""Exceptions métier pour le module promotions."""


class PromoCodeError(Exception):
    """Exception de base pour les erreurs de code promo."""
    default_message = "Erreur code promo."
    default_code = "promo_code_error"

    def __init__(self, message=None, code=None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        super().__init__(self.message)


class InvalidPromoCodeError(PromoCodeError):
    """Le code promo n'existe pas ou n'est pas valide."""
    default_message = "Code promo invalide."
    default_code = "invalid_promo_code"


class PromoExpiredError(PromoCodeError):
    """Le code promo a expiré."""
    default_message = "Ce code promo a expiré."
    default_code = "promo_expired"


class PromoTierRestrictionError(PromoCodeError):
    """Le palier de fidélité de l'utilisateur ne permet pas d'utiliser ce code."""
    default_message = "Votre niveau de fidélité ne permet pas d'utiliser ce code promo."
    default_code = "promo_tier_restricted"


class PromoQuotaExceededError(PromoCodeError):
    """
    Le quota d'utilisation du code promo est atteint.

    Levée notamment par PromoService.apply_code lorsque l'incrément atomique du
    compteur d'utilisations n'affecte aucune ligne (code désactivé entre la
    validation et l'application). L'exception était référencée dans le service
    sans jamais avoir été définie : le premier appel réel levait NameError.
    """
    default_message = "Ce code promo n'est plus disponible."
    default_code = "promo_quota_exceeded"


class PromoUserQuotaExceededError(PromoCodeError):
    """L'utilisateur a déjà consommé ce code promo."""
    default_message = "Vous avez déjà utilisé ce code promo."
    default_code = "promo_user_quota_exceeded"


class FlashSaleError(Exception):
    """Exception de base pour les erreurs de flash sale."""
    pass


class PackError(Exception):
    """Exception de base pour les erreurs liées aux packs."""
    default_message = "Erreur liée au pack promotionnel."
    default_code = "pack_error"

    def __init__(self, message=None, code=None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        super().__init__(self.message)