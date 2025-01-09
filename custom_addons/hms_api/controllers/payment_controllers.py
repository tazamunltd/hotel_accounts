from email.policy import default

from decorator import append

from odoo import http, fields
from odoo.http import request, Response
from datetime import timedelta
from decimal import Decimal
from datetime import datetime
import redis
import json
from io import BytesIO
from zipfile import ZipFile
import arabic_reshaper
from bidi.algorithm import get_display
import platform
from textwrap import wrap

class PaymentController(http.Controller):

    def get_model_data(self, model, columns=None):
        if columns is None:
            columns = []

        records = request.env[model].sudo().search([])
        data = []

        if len(columns) > 1:
            for record in records:
                record_data = {col: getattr(record, col, None) for col in columns}
                data.append(record_data)

        else:
            data = records

        return data

    @http.route('/api/v1/process-payment', type='http', auth='none', methods=['POST'], csrf=False)
    def process_payment(self, **kwargs):
        print("WORKING IN PAYMENT CONTROLLERS")
        print("KWARGS", kwargs)
        payload = json.loads(request.httprequest.data.decode())
        print("BODY", payload)
        return json.dumps({"status": "success"})

    @http.route('/api/signin', type='json', auth='public', methods=['POST'], csrf=False)
    def custom_web_signin(self, **kwargs):
        email = kwargs.get('email')
        mobile = kwargs.get('mobile')
        password = kwargs.get('password')

        if not password or not (email or mobile):
            return {"status": "error", "message": "Missing email, mobile number, or password"}

        # Search by email or mobile
        domain = [('email', '=', email)] if email else [('mobile', '=', mobile)]
        partner = request.env['res.partner'].sudo().search(domain, limit=1)

        if partner and partner.check_password(password):
            session_token = request.session.sid
            return {
                "status": "success",
                "message": "Login successful",
                "session_token": session_token,
                "partner_id": partner.id,
                "email": partner.email
            }
        else:
            return {"status": "error", "message": "Invalid credentials"}

    @http.route('/api/hotels/list', type='json', auth='public', methods=['POST'], csrf=False)
    def get_hotels_list(self, **kwargs):
        companies = request.env['res.company'].sudo().search([])

        all_hotels = []
        for hotel in companies:
            all_hotels.append({
                "id": hotel.id,
                "name": hotel.name
            })

        return {"status": "success", "hotels": all_hotels}