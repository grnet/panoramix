from rest_framework.response import Response
from rest_framework import status as rest_status
from rest_framework.generics import get_object_or_404


class CreateView(object):
    def create(self, request, *args, **kwargs):
        validator = self.get_serializer(data=self.request.data)
        validator.is_valid(raise_exception=True)

        instance = self.creation_logic(request)

        serializer = self.get_serializer(instance)
        return Response(
            serializer.data, status=rest_status.HTTP_201_CREATED)


class PartialUpdateView(object):
    def get_object_for_update(self):
        """
        Returns the object the view is displaying.

        You may want to override this if you need to provide non-standard
        queryset lookups.  Eg if objects are referenced using multiple
        keyword arguments in the url conf.
        """
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.select_for_update()

        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        assert lookup_url_kwarg in self.kwargs, (
            'Expected view %s to be called with a URL keyword argument '
            'named "%s". Fix your URL conf, or set the `.lookup_field` '
            'attribute on the view correctly.' %
            (self.__class__.__name__, lookup_url_kwarg)
        )

        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object_for_update()
        validator = self.get_serializer(
            instance, data=self.request.data, partial=True)
        validator.is_valid(raise_exception=True)

        updated_instance = self.partial_update_logic(request, instance)

        serializer = self.get_serializer(updated_instance)
        return Response(serializer.data)
