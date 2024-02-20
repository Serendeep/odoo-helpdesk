import time
from flask import Flask, request
from flask_restx import Api, Resource, fields, reqparse
import werkzeug
import base64
import dotenv


# Configuration
app = Flask(__name__)
api = Api(app, version='1.0', title='Helpdesk API',
        description='A simple Helpdesk API')
attach_parser = reqparse.RequestParser()
view_parser = reqparse.RequestParser()
email_parser = reqparse.RequestParser()

attach_parser.add_argument('ticket_id', type=int, required=True, help='ID of the ticket')
attach_parser.add_argument('file', location='files',
                                type=werkzeug.datastructures.FileStorage, required=True)
view_parser.add_argument('page', type=int, required=False, default=1, help='Page number')
view_parser.add_argument('limit', type=int, required=False, default=10, help='Number of tickets per page')
email_parser.add_argument('email', type=str, required=True, help='User email address')

# Define a model for your API (if needed, for request parsing)
ticket_model = api.model('Ticket', {
    'name': fields.String(required=True, description='The ticket subject'),
    'description': fields.String(required=True, description='The ticket description'),
    'company_id': fields.Integer(required=True, description='The ID of the company'),
    'email': fields.String(required=True, description='User email for updates')
})

update_ticket_model = api.model('UpdateTicket', {
    'subject': fields.String(description='The updated ticket subject'),
    'description': fields.String(description='The updated ticket description'),
    'stage_id': fields.Integer(description='The updated stage ID of the ticket'),
    'message': fields.String(description='Message to be added to the ticket')
})

# Namespace for tickets
ns = api.namespace('tickets', description='Ticket operations')

import xmlrpc.client
# Configuration
url = dotenv.get_key(".env", "url")
db = dotenv.get_key(".env", "db")
username = dotenv.get_key(".env", "username")
api_key = dotenv.get_key(".env", "api_key")

# Common and Object proxy
common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
version = common.version()
uid = common.authenticate(db, username, api_key, {})
print("Your UID:", uid)
models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))

# Function to delete a ticket
def delete_ticket(ticket_id):
    try:
        result = models.execute_kw(db, uid, api_key, 'helpdesk.ticket', 'unlink', [[ticket_id]])
        return result
    except Exception as e:
        print(f"Error while deleting ticket: {e}")
        return False

def create_ticket(subject, description, company_id):
    context = {
        'force_company': company_id,
        'allowed_company_ids': [company_id],
    }
    try:
        return models.execute_kw(db, uid, api_key,
                                'helpdesk.ticket', 'create', [{
                                    'name': subject,
                                    'description': description,
                                }], {'context': context})
    except Exception as e:
        print(f"Error while creating ticket: {e}")
        return False

# Function to attach a message to the ticket
def attach_message(ticket_id, file_name, base64_content):
    try:
        attachment_id = models.execute_kw(db, uid, api_key, 'ir.attachment', 'create', [{
            'name': file_name,
            'datas': base64_content,
            'store_fname': file_name, 
            'res_model': 'helpdesk.ticket',
            'res_id': ticket_id
        }])
        models.execute_kw(db, uid, api_key, 'mail.message', 'create', [{
            'body': 'Attachment for the ticket',
            'res_id': ticket_id,
            'model': 'helpdesk.ticket',
            'attachment_ids': [(6, 0, [attachment_id])]
        }])
        return attachment_id
    except Exception as e:
        print(f"Error while attaching file to ticket: {e}")
        return False


# Function to update a ticket
def update_ticket(ticket_id, updates):
    try:
        ticket_updates = {k: v for k, v in updates.items() if k != 'message'}
        result = models.execute_kw(db, uid, api_key, 
                                'helpdesk.ticket', 'write', 
                                [[ticket_id], ticket_updates])
        return result
    except Exception as e:
        print(f"Error while updating ticket: {e}")
        return False

# Function to view tickets
def view_tickets(page, limit):
    try:
        offset = (page - 1) * limit
        tickets = models.execute_kw(db, uid, api_key,
            'helpdesk.ticket', 'search_read',
            [[]], {'offset': offset, 'limit': limit, 'fields': ['name', 'description', 'stage_id', 'message_ids']})

        # Optionally, you can also return the total count of tickets for full pagination support
        total_tickets = models.execute_kw(db, uid, api_key, 'helpdesk.ticket', 'search_count', [[]])

        return {
            'tickets': tickets,
            'total': total_tickets
        }
    except Exception as e:
        print(f"Error while viewing tickets: {e}")
        return False

def register_email_in_odoo(email):
    """ 
    Check if the email exists in Odoo, and create a new partner if it doesn't. 
    Returns the partner ID.
    """
    # Check if the email already exists
    partner_id = models.execute_kw(db, uid, api_key, 'res.partner', 'search', [[['email', '=', email]]])
    if not partner_id:
        # Email does not exist, so create a new partner
        partner_id = models.execute_kw(db, uid, api_key, 'res.partner', 'create', [{
            'name': email.split('@')[0],  
            'email': email,
        }])
    else:
        # Email exists, get the first matching ID
        partner_id = partner_id[0]
    return partner_id
    
# Function to view tickets by company
def view_ticket(company_id):
    """
    Function to view tickets for a specific company, returning ticket details if successful, or False if an error occurs.
    
    Parameters:
    - company_id: the ID of the company for which tickets are being viewed (int)
    
    Returns:
    - ticket details if successful (list)
    - False if an error occurs (bool)
    """
    try:
        return models.execute_kw(db, uid, api_key,
            'helpdesk.ticket', 'search_read',
            [[['company_id', '=', company_id]]], {'fields': ['name', 'description', 'stage_id']})
    except Exception as e:
        print(f"Error while viewing tickets: {e}")
        return False

def create_ticket_in_odoo(subject, description, company_id, email):
    """
    Creates a ticket in Odoo with the given subject, description, company ID, and email. Returns the ID of the created ticket.
    """
    context = {
        'force_company': company_id,
        'allowed_company_ids': [company_id],
    }
    partner_id = register_email_in_odoo(email)  
    try:
        ticket_id = models.execute_kw(db, uid, api_key, 'helpdesk.ticket', 'create', [{
            'name': subject,
            'description': description,
            'company_id': company_id,
            'partner_id': partner_id,
        }], {'context': context})
        return ticket_id
    except Exception as e:
        print(f"Error while creating ticket: {e}")
        return False

# Function to list companies
def list_companies():
    return models.execute_kw(db, uid, api_key, 'res.company', 'search_read', [[]], {'fields': ['id', 'name']})

# Create a ticket
@ns.route('/register_email')
class RegisterEmail(Resource):
    @api.expect(email_parser)
    def post(self):
        args = email_parser.parse_args()
        email = args['email']
        partner_id = register_email_in_odoo(email)
        return {'message': 'Email registered successfully', 'partner_id': partner_id}, 201

@ns.route('/create')
class TicketCreate(Resource):
    @api.expect(ticket_model, validate=True)
    def post(self):
        data = api.payload
        ticket_id = create_ticket_in_odoo(data['name'], data['description'], data['company_id'], data['email'])
        return {'ticket_id': ticket_id}, 201

# View all tickets
@ns.route('/view_all')
class TicketList(Resource):
    @ns.expect(view_parser)
    def get(self):
        args = view_parser.parse_args()
        page = args.get('page', 1)
        limit = args.get('limit', 10)
        tickets = view_tickets(page, limit)
        return tickets
    
# Get list of companies with their IDs
@ns.route('/list_companies')
class CompanyList(Resource):
    def get(self):
        companies = list_companies()
        return companies

# Attach file to a ticket
@ns.route('/attach_file')
class AttachFile(Resource):
    @api.expect(attach_parser)
    def post(self):
        file_upload = attach_parser.parse_args()
        uploaded_file = file_upload['file']
        file_content = base64.b64encode(uploaded_file.read()).decode('utf-8')
        args = attach_parser.parse_args()
        ticket_id = args['ticket_id']
        file_content = file_content

        result = attach_message(ticket_id,uploaded_file.filename,file_content)
        return {'result': result}, 200

# Update a ticket
@ns.route('/update/<int:ticket_id>')
class TicketUpdate(Resource):
    @api.expect(update_ticket_model, validate=True)
    def put(self, ticket_id):
        updates = api.payload
        result = update_ticket(ticket_id, updates)

        if result:
            response_message = 'Ticket updated successfully'

            if 'message' in updates and updates['message']:
                models.execute_kw(db, uid, api_key, 'mail.message', 'create', [{
                'body': updates['message'],
                'res_id': ticket_id,
                'model': 'helpdesk.ticket'
            }])

            return {'message': response_message}, 200
        else:
            return {'message': 'Failed to update ticket'}, 400

# Delete a ticket
@ns.route('/delete/<int:ticket_id>')
class TicketDelete(Resource):
    def delete(self, ticket_id):
        result = delete_ticket(ticket_id)
        if result:
            return {'message': 'Ticket deleted successfully'}, 200
        else:
            return {'message': 'Failed to delete ticket'}, 400

# Get tickets by company ID
@ns.route('/by_company/<int:company_id>')
class TicketsByCompany(Resource):
    def get(self, company_id):
        tickets = view_ticket(company_id)
        return tickets
    
if __name__ == '__main__':
    app.run(debug=True)