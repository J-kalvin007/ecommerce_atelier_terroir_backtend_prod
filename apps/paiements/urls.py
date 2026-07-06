from django.urls import path

from .api.views import paydunya_webhook, InitializePaydunyaPaymentView, RechargeWalletPaydunyaPaymentView
from .views import (
    WalletBalanceView,
    WalletDepositView,
    WalletPayView,
    WalletTransactionsView,
    PaymentInitiateView,
    PayDunyaWebhookView,
    AdminWithdrawView,
    OrderRefundView,
    AdminAllTransactionsView,
    AdminWalletListView,
    AdminWalletStatusUpdateView,
)

urlpatterns = [

    path(
        "my-wallet/",
        WalletBalanceView.as_view(),
        name="wallet-balance",
    ),

    path(
        "wallet/deposit/",
        WalletDepositView.as_view(),
        name="wallet-deposit",
    ),

    path(
        "wallet/achat/",
        WalletPayView.as_view(),
        name="wallet-pay",
    ),

    path(
        "wallet/historique-transactions/",
        WalletTransactionsView.as_view(),
        name="wallet-historique-transactions",
    ),

    path(
        "initier-paiement-direct/",
        InitializePaydunyaPaymentView.as_view(),
        name="initier-paiement-direct",
    ),

    path(
        "recharge-user-wallet/",
        RechargeWalletPaydunyaPaymentView.as_view(),
        name="recharge-wallet-direct",
    ),


    path(
        "remboursement-commande/",
        OrderRefundView.as_view(),
        name="remboursement-commande",
    ),

    path(
        "admin/all-transactions/",
        AdminAllTransactionsView.as_view(),
        name="all-transactions",
    ),

    path(
        "admin/all-wallets/",
        AdminWalletListView.as_view(),
        name="admin-all-wallets",
    ),

    path(
        "admin/wallets/<uuid:pk>/status/",
        AdminWalletStatusUpdateView.as_view(),
        name="admin-wallets-status-update",
    ),


    path("ipn/", paydunya_webhook, name="paydunya_ipn"),
]
