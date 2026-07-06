from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.mixins import UpdateModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.core.permissions import IsPlatformAdmin
from ecommerce_backend.users.models import User

from .serializers import UserSerializer


class UserViewSet(RetrieveModelMixin, ListModelMixin, UpdateModelMixin, GenericViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all()
    lookup_field = "pk"

    def get_queryset(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            if getattr(self.request.user, "role", None) == "platform_admin" or self.request.user.is_superuser:
                return self.queryset.exclude(is_superuser=True)
            return self.queryset.filter(id=self.request.user.id)
        return self.queryset.none()

    @action(detail=False)
    def me(self, request):
        serializer = UserSerializer(request.user, context={"request": request})
        return Response(status=status.HTTP_200_OK, data=serializer.data)

    @action(detail=False, url_path="all-users", permission_classes=[IsPlatformAdmin])
    def all_users(self, request):
        users = User.objects.exclude(is_superuser=True)
        
        # Paginate results if pagination is configured on the viewset
        page = self.paginate_queryset(users)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(users, many=True)
        return Response(status=status.HTTP_200_OK, data=serializer.data)
