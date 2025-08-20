from odoo import http
from odoo.http import Response, request

class CorsController(http.Controller):
    @http.route('/cors/<path:path>', type='http', auth='none', csrf=False, save_session=False)
    def cors_proxy(self, path, **kwargs):
        response = request.make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'OPTIONS, GET, POST, PUT, DELETE'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, X-Requested-With, Content-Type, Accept, Authorization'
        return response

    @http.route('/cors/<path:path>', type='http', auth='none', csrf=False, methods=['OPTIONS'])
    def preflight(self, path, **kwargs):
        return self.cors_proxy(path, **kwargs)
