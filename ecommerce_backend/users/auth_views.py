

from dj_rest_auth.views import LoginView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from .serializers import UserSerializer


class LoginResponseSerializer(serializers.Serializer):
    key = serializers.CharField()
    user = UserSerializer()


@extend_schema(
    responses=LoginResponseSerializer
)
class CustomLoginView(LoginView):

    def get_response(self):

        original_response = super().get_response()

        token = original_response.data["key"]

        user_data = UserSerializer(
            self.user,
            context=self.get_serializer_context(),
        ).data

        return Response(
            {
                "key": token,
                "user": user_data,
            }
        )







# class CustomLoginView(LoginView):

#     def get_response(self):

#         original_response = super().get_response()

#         token = original_response.data["key"]

#         user_data = UserSerializer(
#             self.user,
#             context=self.get_serializer_context(),
#         ).data

#         return Response(
#             {
#                 "key": token,
#                 "user": user_data,
#             }
#         )






# class CustomLoginView(LoginView):

#     def get_response(self):

#         response = super().get_response()

#         user_data = UserSerializer(
#             self.user
#         ).data

#         response.data["user"] = user_data

#         return response



