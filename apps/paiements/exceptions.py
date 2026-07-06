"""
Exceptions métier pour le module de paiement.
"""


class InsufficientBalanceError(Exception):
    """Levée lorsqu'un paiement ne peut être couvert par le solde du wallet."""
    pass


class WalletInactiveError(Exception):
    """Le wallet n'est pas en état d'effectuer des opérations (suspendu, bloqué ou inexistant)."""
    pass


class PaymentAlreadyProcessedError(Exception):
    """Tentative de traiter un paiement déjà finalisé (idempotence)."""
    pass


class PaymentGatewayError(Exception):
    """Erreur générique lors d'un appel à une passerelle de paiement."""
    pass