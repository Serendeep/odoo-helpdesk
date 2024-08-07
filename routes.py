import base64
from flask import request
from flask_restx import Namespace, Resource, abort
from models import attach_parser, view_parser, email_parser, ticket_model, update_ticket_model
from services import (create_ticket_in_odoo, delete_ticket, attach_message, get_mail_templates, get_messages_by_ticket_id, send_email_odoo, 
                    update_ticket, view_tickets, list_companies, 
                    view_ticket, register_email_in_odoo, get_tickets_by_user, get_ticket_by_id)
from app import api

tickets_ns = Namespace('tickets', description='Ticket operations')


@tickets_ns.route('/healthcheck')
class ExampleResource(Resource):
    def get(self):
        """Return a simple 'OK' message."""
        return {"message": "OK"}, 200
    
@tickets_ns.route('/mail_templates')
class MailTemplates(Resource):
    def get(self):
        """Return a list of mail templates from Odoo."""
        templates = get_mail_templates()
        if templates is not None:
            return {'templates': templates}, 200
        else:
            return {'message': 'Failed to fetch mail templates from Odoo.'}, 500

@tickets_ns.route('/register_email')
class RegisterEmail(Resource):
    @tickets_ns.expect(email_parser)
    def post(self):
        """Register an email in Odoo."""
        args = email_parser.parse_args()
        try:
            partner_id = register_email_in_odoo(args['email'])
            if not partner_id:
                abort(400, 'Failed to register email.')
            return {'message': 'Email registered successfully', 'partner_id': partner_id}, 201
        except Exception as e:
            abort(500, str(e))

@tickets_ns.route('/create')
class TicketCreate(Resource):
    @tickets_ns.expect(ticket_model, validate=True)
    def post(self):
        """Create a ticket in Odoo."""
        data = api.payload
        try:
            ticket_id = create_ticket_in_odoo(**data)
            if not ticket_id:
                abort(400, 'Failed to create ticket.')
            else:
                if not send_email_odoo(18, ticket_id, data.get('company_id')):
                    print("Email sending failed.")
                return {'ticket_id': ticket_id}, 201
        except Exception as e:
            abort(500, str(e))

@tickets_ns.route('/view_all')
class TicketList(Resource):
    @tickets_ns.expect(view_parser)
    def get(self):
        """Retrieve paginated tickets in Odoo."""
        args = view_parser.parse_args()
        try:
            tickets_info = view_tickets(args['page'], args['limit'])
            return tickets_info
        except Exception as e:
            abort(500, str(e))

@tickets_ns.route('/list_companies')
class CompanyList(Resource):
    """List paginated companies in Odoo."""
    @tickets_ns.expect(view_parser)
    def get(self):
        args = view_parser.parse_args()
        try:
            companies = list_companies(args['page'], args['limit'])
            return companies
        except Exception as e:
            abort(500, str(e))

@tickets_ns.route('/attach_file')
class AttachFile(Resource):
    @tickets_ns.expect(attach_parser)
    def post(self):
        """Attach a file to a ticket in Odoo."""
        args = attach_parser.parse_args()
        try:
            uploaded_file = args['file']
            file_content = base64.b64encode(uploaded_file.read()).decode('utf-8')
            result = attach_message(args['ticket_id'], uploaded_file.filename, file_content)
            if not result:
                abort(400, 'Failed to attach file.')
            return {'result': result}, 200
        except Exception as e:
            abort(500, str(e))

@tickets_ns.route('/update/<int:ticket_id>')
class TicketUpdate(Resource):
    @tickets_ns.expect(update_ticket_model, validate=True)
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
    def delete(self, ticket_id):
        """Delete a ticket in Odoo."""
        try:
            if delete_ticket(ticket_id):
                return {'message': 'Ticket deleted successfully'}, 200
            abort(400, 'Failed to delete ticket.')
        except Exception as e:
            abort(500, str(e))

@tickets_ns.route('/by_company/<int:company_id>')
class TicketsByCompany(Resource):
    @tickets_ns.expect(view_parser)
    def get(self, company_id):
        """Retrieve paginated tickets associated with a specific company ID."""
        args = view_parser.parse_args()
        try:
            tickets_info = view_ticket(company_id, args['page'], args['limit'])
            if tickets_info:
                return tickets_info, 200
            else:
                return {'message': 'Failed to fetch tickets for the company.'}, 500
        except Exception as e:
            abort(500, str(e))

@tickets_ns.route('/by_user/<int:user_id>')
class TicketsByUser(Resource):
    @tickets_ns.expect(view_parser)
    def get(self, user_id):
        """Retrieve paginated tickets associated with a specific user ID."""
        args = view_parser.parse_args()
        try:
            tickets_info = get_tickets_by_user(user_id, args['page'], args['limit'])
            if tickets_info:
                return tickets_info, 200
            else:
                return {'message': 'Failed to fetch tickets for the user.'}, 500
        except Exception as e:
            abort(500, str(e))

@tickets_ns.route('/<int:ticket_id>')
class TicketByID(Resource):
    def get(self, ticket_id):
        """Retrieve a ticket by its ID."""
        try:
            ticket = get_ticket_by_id(ticket_id)
            if ticket:
                return {'ticket': ticket}, 200
            else:
                return {'message': 'Ticket not found'}, 404
        except Exception as e:
            abort(500, str(e))
            
@tickets_ns.route('/message/<int:ticket_id>')
class TicketMessage(Resource):
    def get(self, ticket_id):
        """Retrieve ticket messages by its ID."""
        try:
            ticket = get_messages_by_ticket_id(ticket_id)
            if ticket:
                return {'ticket': ticket}, 200
            else:
                return {'message': 'Ticket not found'}, 404
        except Exception as e:
            abort(500, str(e))