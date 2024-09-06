import base64
from flask import request
from flask_restx import Namespace, Resource, abort
from models import attach_parser, view_parser, ticket_model, update_ticket_model, public_ticket_model, email_parser, ticket_message, message_model, templates_model, ticket_create_model, ticket_list_model, ticket_dict_model
from services import (
    add_message_to_ticket, create_ticket_in_odoo, delete_ticket, attach_message, get_mail_templates, 
    get_messages_by_ticket_id, get_ticket_stages, get_tickets_by_email, get_tickets_by_user, get_tickets_data, 
    send_email_odoo, update_customer_email, update_ticket, list_companies, get_ticket_by_id, view_ticket
)
from app import api
from utils import auth_required

tickets_ns = Namespace('tickets', description='Ticket operations')

@tickets_ns.route('/healthCheck')
class ExampleResource(Resource):
    @api.response(200, 'OK', message_model)
    @api.response(500, 'Internal Server Error', message_model)
    def get(self):
        """Return a simple 'OK' message."""
        return {"message": "OK"}, 200

@api.hide
@tickets_ns.route('/mailTemplates')
class MailTemplates(Resource):
    @api.response(200, 'Mail Templates Fetched Successfully', templates_model)
    @api.response(500, 'Failed to Fetch Mail Templates', message_model)
    def get(self):
        """Return a list of mail templates from Odoo."""
        templates = get_mail_templates()
        if templates:
            return {'templates': templates}, 200
        return {'message': 'Failed to fetch mail templates from Odoo.'}, 500

@tickets_ns.route('/create')
class TicketCreate(Resource):
    @api.doc(security='Bearer')
    @auth_required
    @tickets_ns.expect(ticket_model, validate=True)
    @api.response(201, 'Ticket Created', ticket_create_model)
    @api.response(400, 'Failed to Create Ticket', message_model)
    @api.response(401, 'Unauthorized', message_model)
    @api.response(500, 'Internal Server Error', message_model)
    def post(self):
        """Create a ticket in Odoo."""
        data = api.payload
        try:
            decrypted_data = request.decrypted_data 
            data['company_id'] = decrypted_data['company_id'] 
            data['email'] = decrypted_data['email']
            
            ticket_id = create_ticket_in_odoo(**data)
            if not ticket_id:
                abort(400, 'Failed to create ticket.')
            email_sent = send_email_odoo(18, ticket_id, data.get('company_id'))
            return {'ticket_id': ticket_id, 'email_sent': email_sent}, 201
        except Exception as e:
            abort(500, str(e))

@tickets_ns.route('/create/public')
class PublicTicketCreate(Resource):
    @tickets_ns.expect(public_ticket_model, validate=True)
    @api.response(201, 'Public Ticket Created', ticket_create_model)
    @api.response(400, 'Failed to Create Public Ticket', message_model)
    @api.response(500, 'Internal Server Error', message_model)
    def post(self):
        """Create a public ticket in Odoo."""
        data = api.payload
        try:
            ticket_id = create_ticket_in_odoo(**data)
            if not ticket_id:
                abort(400, 'Failed to create ticket.')
            email_sent = send_email_odoo(18, ticket_id, data.get('company_id'))
            return {'ticket_id': ticket_id, 'email_sent': email_sent}, 201
        except Exception as e:
            abort(500, str(e))

@api.hide
@tickets_ns.route('/viewAll/<int:company_id>')
class TicketList(Resource):
    @tickets_ns.expect(view_parser)
    @api.response(200, 'Tickets Fetched Successfully', ticket_list_model)
    @api.response(500, 'Internal Server Error', message_model)
    def get(self, company_id):
        """Retrieve paginated tickets in Odoo."""
        args = view_parser.parse_args()
        try:
            tickets_info = view_ticket(company_id, args['page'], args['limit'])
            return {'tickets': tickets_info}, 200
        except Exception as e:
            abort(500, str(e))

@api.hide
@tickets_ns.route('/listCompanies')
class CompanyList(Resource):
    @tickets_ns.expect(view_parser)
    @api.response(200, 'Companies Listed Successfully')
    @api.response(500, 'Internal Server Error', message_model)
    def get(self):
        """List paginated companies in Odoo."""
        args = view_parser.parse_args()
        try:
            companies = list_companies(args['page'], args['limit'])
            return {'companies': companies}, 200
        except Exception as e:
            abort(500, str(e))

@tickets_ns.route('/attachFile')
class AttachFile(Resource):
    @tickets_ns.expect(attach_parser)
    @api.doc(security='Bearer')
    @auth_required
    @api.response(200, 'File Attached Successfully', message_model)
    @api.response(400, 'Failed to Attach File', message_model)
    @api.response(401, 'Unauthorized', message_model)
    @api.response(500, 'Internal Server Error', message_model)
    def post(self):
        """Attach a file to a ticket in Odoo."""
        args = attach_parser.parse_args()
        try:
            uploaded_file = args['file']
            file_content = base64.b64encode(uploaded_file.read()).decode('utf-8')
            result = attach_message(args['ticket_id'], uploaded_file.filename, file_content)
            if not result:
                abort(400, 'Failed to attach file.')
            return {'message': result}, 200
        except Exception as e:
            abort(500, str(e))

@tickets_ns.route('/update/<int:ticket_id>')
class TicketUpdate(Resource):
    @tickets_ns.expect(update_ticket_model, validate=True)
    @api.doc(security='Bearer')
    @auth_required
    @api.response(200, 'Ticket Updated Successfully', message_model)
    @api.response(400, 'Failed to Update Ticket', message_model)
    @api.response(401, 'Unauthorized', message_model)
    @api.response(500, 'Internal Server Error', message_model)
    def put(self, ticket_id):
        """Update a ticket in Odoo."""
        updates = api.payload
        try:
            result = update_ticket(ticket_id, updates)
            if not result:
                abort(400, 'Failed to update ticket.')
            return {'message': 'Ticket updated successfully'}, 200
        except Exception as e:
            abort(500, str(e))

@tickets_ns.route('/delete/<int:ticket_id>')
class TicketDelete(Resource):
    @api.doc(security='Bearer')
    @auth_required
    @api.response(200, 'Ticket Deleted Successfully', message_model)
    @api.response(400, 'Failed to Delete Ticket', message_model)
    @api.response(401, 'Unauthorized', message_model)
    @api.response(500, 'Internal Server Error', message_model)
    def delete(self, ticket_id):
        """Delete a ticket in Odoo."""
        try:
            if delete_ticket(ticket_id):
                return {'message': 'Ticket deleted successfully'}, 200
            abort(400, 'Failed to delete ticket.')
        except Exception as e:
            abort(500, str(e))

@api.hide
@tickets_ns.route('/byCompany/<int:company_id>')
class TicketsByCompany(Resource):
    @tickets_ns.expect(view_parser)
    @api.response(200, 'Tickets Fetched Successfully', ticket_list_model)
    @api.response(500, 'Internal Server Error', message_model)
    def get(self, company_id):
        """Retrieve paginated tickets associated with a specific company ID."""
        args = view_parser.parse_args()
        try:
            tickets_info = view_ticket(company_id, args['page'], args['limit'])
            if tickets_info:
                return {'tickets': tickets_info}, 200
            return {'message': 'Failed to fetch tickets for the company.'}, 500
        except Exception as e:
            abort(500, str(e))

@api.hide
@tickets_ns.route('/byUser/<int:user_id>')
class TicketsByUser(Resource):
    @tickets_ns.expect(view_parser)
    @api.response(200, 'Tickets Fetched Successfully', ticket_list_model)
    @api.response(500, 'Internal Server Error', message_model)
    def get(self, user_id):
        """Retrieve paginated tickets associated with a specific user ID."""
        args = view_parser.parse_args()
        try:
            tickets_info = get_tickets_by_user(user_id, args['page'], args['limit'])
            if tickets_info:
                return {'tickets': tickets_info}, 200
            return {'message': 'Failed to fetch tickets for the user.'}, 500
        except Exception as e:
            abort(500, str(e))

@tickets_ns.route('/<int:ticket_id>')
class TicketByID(Resource):
    @api.doc(security='Bearer')
    @auth_required
    @api.response(200, 'Ticket Fetched Successfully', ticket_dict_model)
    @api.response(401, 'Unauthorized', message_model)
    @api.response(404, 'Ticket Not Found', message_model)
    @api.response(500, 'Internal Server Error', message_model)
    def get(self, ticket_id):
        """Retrieve a ticket by its ID."""
        try:
            ticket = get_ticket_by_id(ticket_id)
            if ticket:
                return {'ticket': ticket}, 200
            return {'message': 'Ticket not found'}, 404
        except Exception as e:
            abort(500, str(e))

@api.hide
@tickets_ns.route('/message/<int:ticket_id>')
class TicketMessage(Resource):
    @api.doc(security='Bearer')
    @auth_required
    @api.response(200, 'Ticket Messages Fetched Successfully')
    @api.response(401, 'Unauthorized', message_model)
    @api.response(404, 'Ticket Not Found', message_model)
    @api.response(500, 'Internal Server Error', message_model)
    def get(self, ticket_id):
        """Retrieve ticket messages by its ID."""
        try:
            messages = get_messages_by_ticket_id(ticket_id)
            if messages:
                return {'messages': messages}, 200
            return {'message': 'Ticket not found'}, 404
        except Exception as e:
            abort(500, str(e))

@tickets_ns.route('/byEmail')
class TicketsByEmail(Resource):
    @api.doc(security='Bearer')
    @auth_required
    @tickets_ns.expect(view_parser)
    @api.response(200, 'Tickets Fetched Successfully', ticket_list_model)
    @api.response(401, 'Unauthorized', message_model)
    @api.response(500, 'Internal Server Error', message_model)
    def get(self):
        """Retrieve paginated tickets associated with a specific email."""
        args = view_parser.parse_args()
        page = args.get('page', 1)
        limit = args.get('limit', 10)

        try:
            decrypted_data = request.decrypted_data
            email = decrypted_data.get('email')
            company_id = decrypted_data.get('company_id')
            
            tickets_info = get_tickets_by_email(email, company_id, page, limit)
            if tickets_info:
                return {'tickets': tickets_info}, 200
            return {'message': 'Failed to fetch tickets for the email.'}, 500
        except Exception as e:
            abort(500, str(e))

@api.hide
@tickets_ns.route('/stages')
class TicketStages(Resource):
    @api.response(200, 'Ticket Stages Fetched Successfully')
    @api.response(500, 'Failed to Fetch Ticket Stages', message_model)
    def get(self):
        """Retrieve ticket stages from Odoo."""
        try:
            stages = get_ticket_stages()
            if stages:
                return {'stages': stages}, 200
            return {'message': 'Failed to fetch ticket stages.'}, 500
        except Exception as e:
            abort(500, str(e))

@tickets_ns.route('/getTicketData')
class GetTicketData(Resource):
    @tickets_ns.expect(view_parser)
    @api.doc(security='Bearer')
    @auth_required
    @api.response(200, 'Ticket Data Fetched Successfully', ticket_list_model)
    @api.response(401, 'Unauthorized', message_model)
    @api.response(500, 'Failed to Fetch Ticket Data', message_model)
    def get(self):
        """Retrieve paginated tickets associated with a specific email."""
        args = view_parser.parse_args()
        page = args.get('page', 1)
        limit = args.get('limit', 10)
        
        decrypted_data = request.decrypted_data
        email = decrypted_data.get('email')
        company_id = decrypted_data.get('company_id')
        
        try:
            tickets_info = get_tickets_data(email, company_id, page, limit)
            if tickets_info:
                return {'tickets': tickets_info}, 200
            return {'message': 'Failed to fetch tickets for the email.'}, 500
        except Exception as e:
            abort(500, str(e))

@tickets_ns.route('/updateCustomerEmail')
class UpdateCustomerEmail(Resource):
    @tickets_ns.expect(email_parser)
    @api.doc(security='Bearer')
    @auth_required
    @api.response(200, 'Customer Email Updated Successfully', message_model)
    @api.response(401, 'Unauthorized', message_model)
    @api.response(500, 'Failed to Update Customer Email', message_model)
    def post(self):
        """Update customer email in Odoo."""
        args = view_parser.parse_args()
        new_email = args.get('new_email')
        
        decrypted_data = request.decrypted_data
        email = decrypted_data.get('email')
        company_id = decrypted_data.get('company_id')
        
        try:
            email = update_customer_email(email, new_email, company_id)
            if email:
                return {'message': 'Customer email updated successfully.'}, 200
            return {'message': 'Failed to update customer email.'}, 500
        except Exception as e:
            abort(500, str(e))

@tickets_ns.route('/ticketMessage')
class TicketMessage(Resource):
    @tickets_ns.expect(ticket_message)
    @api.doc(security='Bearer')
    @auth_required
    @api.response(200, 'Message Added Successfully', message_model)
    @api.response(401, 'Unauthorized', message_model)
    @api.response(500, 'Failed to Add Message', message_model)
    def post(self):
        """Create a ticket message in Odoo."""
        data = api.payload
        
        decrypted_data = request.decrypted_data
        email = decrypted_data.get('email')
        company_id = decrypted_data.get('company_id')
        
        try:
            message = add_message_to_ticket(email, company_id, **data)
            
            if message:
                return {'message': 'Message added successfully.'}, 200
            return {'message': 'Failed to add message.'}, 500
        except Exception as e:
            abort(500, str(e))
