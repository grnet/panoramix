import traceback


class ExceptionMiddleware(object):
    def process_exception(self, request, exception):
        traceback.print_exc()
