from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    Custom exception handler providing uniform JSON error responses.
    """
    response = exception_handler(exc, context)

    if response is not None:
        # Structure de base de l'erreur
        custom_data = {
            'success': False,
            'error_type': exc.__class__.__name__,
            'detail': response.data
        }

        # Si response.data est un dictionnaire contenant un champ 'detail',
        # on l'utilise comme message principal pour plus de clarté.
        if isinstance(response.data, dict) and 'detail' in response.data:
            custom_data['detail'] = response.data['detail']

        response.data = custom_data

    return response