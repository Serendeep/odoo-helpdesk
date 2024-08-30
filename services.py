import re
import xmlrpc.client
import logging
from config import URL, DB, USERNAME, API_KEY

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

common_proxy = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
uid = common_proxy.authenticate(DB, USERNAME, API_KEY, {})
object_proxy = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')

def execute_kw(model, method, args, kwargs=None):
    """Execute a method on an Odoo model via XML-RPC, with error handling."""
    try:
        if not uid:
            raise ValueError("User ID is invalid. Please authenticate first.")
        return object_proxy.execute_kw(DB, uid, API_KEY, model, method, args, kwargs or {})
    except xmlrpc.client.Fault as fault:
        logger.error(f"XML-RPC Fault Error on {model}.{method}: {fault.faultString}", exc_info=True)
    except xmlrpc.client.ProtocolError as err:
        logger.error(f"Protocol Error while connecting to {model}.{method}: {err.errmsg}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error on {model}.{method}: {e}", exc_info=True)
    return None

def authenticate():
    """Retrieve the server version and user ID for the session."""
    try:
        version = common_proxy.version()
        logger.info("Successfully authenticated with Odoo.")
        return version, uid
    except xmlrpc.client.Fault as fault:
        logger.error(f"Authentication XML-RPC Fault: {fault.faultString}", exc_info=True)
    except Exception as e:
        logger.error(f"Authentication Error: {e}", exc_info=True)
    return None, None

def create_ticket_in_odoo(subject, description, company_id, email):
    """Create a new ticket in Odoo."""
    try:
        partner_id = register_email_in_odoo(email, company_id)
        if not partner_id:
            logger.warning("Could not create ticket due to missing partner.")
            return None
        context = {'force_company': company_id, 'allowed_company_ids': [company_id]}
        ticket_id = execute_kw('helpdesk.ticket', 'create', [{
            'name': subject,
            'description': description,
            'company_id': company_id,
            'partner_id': partner_id,
        }], {'context': context})
        if ticket_id:
            logger.info(f"Ticket created with ID: {ticket_id}")
        else:
            logger.error("Failed to create ticket.")
        return ticket_id
    except Exception as e:
        logger.error(f"Error creating ticket: {e}", exc_info=True)
        return None

def delete_ticket(ticket_id):
    """Delete a ticket in Odoo."""
    try:
        if execute_kw('helpdesk.ticket', 'unlink', [[ticket_id]]):
            logger.info(f"Ticket with ID {ticket_id} deleted.")
            return True
        else:
            logger.warning(f"Failed to delete ticket with ID {ticket_id}.")
    except Exception as e:
        logger.error(f"Error deleting ticket: {e}", exc_info=True)
    return False

def attach_message(ticket_id, file_name, base64_content):
    """Attach a message to a ticket in Odoo."""
    try:
        attachment_id = execute_kw('ir.attachment', 'create', [{
            'name': file_name,
            'datas': base64_content,
            'store_fname': file_name,
            'res_model': 'helpdesk.ticket',
            'res_id': ticket_id
        }])
        if attachment_id:
            execute_kw('mail.message', 'create', [{
                'body': 'Attachment for the ticket',
                'res_id': ticket_id,
                'model': 'helpdesk.ticket',
                'attachment_ids': [(6, 0, [attachment_id])]
            }])
            logger.info(f"Attachment created with ID: {attachment_id} for ticket ID: {ticket_id}")
        else:
            logger.error("Failed to create attachment.")
        return attachment_id
    except Exception as e:
        logger.error(f"Error attaching message: {e}", exc_info=True)
        return None

def update_ticket(ticket_id, updates):
    """Update a ticket in Odoo."""
    try:
        if not ticket_id or not updates:
            logger.error("Ticket ID or updates are missing.")
            return False
        ticket_updates = {k: v for k, v in updates.items() if k != 'message'}
        result = execute_kw('helpdesk.ticket', 'write', [[ticket_id], ticket_updates])
        if 'message' in updates and updates['message']:
            execute_kw('mail.message', 'create', [{
                'body': updates['message'],
                'res_id': ticket_id,
                'model': 'helpdesk.ticket'
            }])
        return result
    except Exception as e:
        logger.error(f"Error while updating ticket: {e}", exc_info=True)
        return False

def send_email_odoo(template_id, ticket_id, company_id):
    """Send an email using a predefined Odoo email template."""
    try:
        context = {'force_company': company_id, 'allowed_company_ids': [company_id]}
        sent = execute_kw('mail.template', 'send_mail', [template_id, ticket_id], {'context': context})
        if sent:
            logger.info("Email successfully sent through Odoo.")
            return True
        else:
            logger.warning(f"Failed to send email for ticket ID: {ticket_id}.")
    except Exception as e:
        logger.error(f"Failed to send email: {e}", exc_info=True)
    return False

def get_mail_templates():
    """Fetch mail templates from Odoo."""
    try:
        templates = execute_kw('mail.template', 'search_read', [[]], {'fields': ['id', 'name', 'model']})
        return templates if templates else []
    except Exception as e:
        logger.error(f"Error fetching mail templates from Odoo: {e}", exc_info=True)
        return []

def view_tickets(page, limit):
    """View a paginated list of tickets."""
    try:
        if page < 1 or limit < 1:
            logger.error("Invalid pagination parameters.")
            return {'tickets': [], 'total': 0}
        offset = (page - 1) * limit
        tickets = execute_kw('helpdesk.ticket', 'search_read', [[]], {
            'offset': offset, 'limit': limit, 'fields': ['name', 'description', 'stage_id', 'message_ids']})
        total_tickets = execute_kw('helpdesk.ticket', 'search_count', [[]])
        return {'tickets': tickets, 'total': total_tickets}
    except Exception as e:
        logger.error(f"Error viewing tickets: {e}", exc_info=True)
        return {'tickets': [], 'total': 0}

def validate_email_format(email):
    """Validates the email format using a regex."""
    email_regex = r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
    if not re.match(email_regex, email):
        logging.error(f"Invalid email format: {email}")
        raise ValueError("Invalid email format.")
    logging.info(f"Email format validated: {email}")

def register_email_in_odoo(email, company_id):
    """Register an email in Odoo, creating a new partner if necessary."""
    try:
        if not email or not company_id:
            logger.error("Email or company_id is missing.")
            return None
        
        # Validate email
        validate_email_format(email)
        
        # Search for existing partner with the given email and company ID
        partner_id = execute_kw('res.partner', 'search', [[['email', '=', email], ['company_id', '=', company_id]]])
        
        if not partner_id:
            # If no partner is found, create a new one
            partner_id = [execute_kw('res.partner', 'create', [{'name': email.split('@')[0], 'email': email, 'company_id': company_id}])]
            logger.info(f"New partner created with ID: {partner_id[0]} for email: {email} in company ID: {company_id}")
        
        return partner_id[0]
    except ValueError as ve:
        logger.error(f"Email format error: {ve}")
        return None
    except Exception as e:
        logger.error(f"Error registering email: {e}", exc_info=True)
        return None

def view_ticket(company_id, page, limit):
    """View paginated tickets for a specific company."""
    try:
        if page < 1 or limit < 1:
            logger.error("Invalid pagination parameters.")
            return {'tickets': [], 'total': 0}
        offset = (page - 1) * limit
        tickets = execute_kw('helpdesk.ticket', 'search_read', 
                            [[['company_id', '=', company_id]]], 
                            {'offset': offset, 'limit': limit, 'fields': ['name', 'description', 'stage_id', 'email', 'company_id']})
        total_tickets = execute_kw('helpdesk.ticket', 'search_count', [[['company_id', '=', company_id]]])
        return {'tickets': tickets, 'total': total_tickets}
    except Exception as e:
        logger.error(f"Error fetching tickets for company ID {company_id}: {e}", exc_info=True)
        return {'tickets': [], 'total': 0}

def list_companies(page, limit):
    """List paginated companies in Odoo."""
    try:
        if page < 1 or limit < 1:
            logger.error("Invalid pagination parameters.")
            return {'companies': [], 'total': 0}
        offset = (page - 1) * limit
        companies = execute_kw('res.company', 'search_read', [[]], {
            'offset': offset,
            'limit': limit,
            'fields': ['id', 'name']
        })
        total_companies = execute_kw('res.company', 'search_count', [[]])
        return {'companies': companies, 'total': total_companies}
    except Exception as e:
        logger.error(f"Error listing companies: {e}", exc_info=True)
        return {'companies': [], 'total': 0}

def get_tickets_by_user(user_id, page, limit):
    """Fetch paginated tickets for a specific user from Odoo."""
    try:
        if page < 1 or limit < 1:
            logger.error("Invalid pagination parameters.")
            return {'tickets': [], 'total': 0}
        offset = (page - 1) * limit
        tickets = execute_kw('helpdesk.ticket', 'search_read', 
                            [[['partner_id', '=', user_id]]], 
                            {'offset': offset, 'limit': limit, 'fields': ['id', 'name', 'description', 'stage_id']})
        total_tickets = execute_kw('helpdesk.ticket', 'search_count', [[['partner_id', '=', user_id]]])
        return {'tickets': tickets, 'total': total_tickets}
    except Exception as e:
        logger.error(f"Error fetching tickets for user ID {user_id}: {e}", exc_info=True)
        return {'tickets': [], 'total': 0}

def get_ticket_by_id(ticket_id):
    """Fetch a ticket by its ID from Odoo."""
    try:
        ticket = execute_kw('helpdesk.ticket', 'search_read', 
                            [[['id', '=', ticket_id]]], 
                            {'fields': ['id', 'name', 'description', 'stage_id', 'partner_id']})
        if ticket:
            messages = execute_kw('mail.message', 'search_read', 
                                [[['res_id', '=', ticket_id], ['model', '=', 'helpdesk.ticket']]], 
                                {'fields': ['id', 'body', 'date', 'author_id']})
            ticket[0]['messages'] = messages[:-1]
            return ticket[0]
        else:
            logger.warning(f"No ticket found with ID: {ticket_id}")
            return None
    except Exception as e:
        logger.error(f"Error fetching ticket with ID {ticket_id}: {e}", exc_info=True)
        return None

def get_messages_by_ticket_id(ticket_id):
    """Fetch messages by ticket ID from Odoo."""
    try:
        messages = execute_kw('mail.message', 'search_read', 
                            [[['res_id', '=', ticket_id]]], 
                            {'fields': ['id', 'body', 'date', 'author_id']})
        return messages if messages else []
    except Exception as e:
        logger.error(f"Error fetching messages for ticket with ID {ticket_id}: {e}", exc_info=True)
        return []

def get_tickets_by_email(email, company_id, page=1, limit=10):
    """Fetch paginated tickets by email and company_id from Odoo."""
    try:
        partner_id = execute_kw('res.partner', 'search', [[['email', '=', email], ['company_id', '=', company_id]]])
        if not partner_id:
            logger.error(f"No partner found with email: {email} and company_id: {company_id}")
            return {'tickets': [], 'total': 0}
        
        offset = (page - 1) * limit
        tickets = execute_kw('helpdesk.ticket', 'search_read', 
                            [[['partner_id', '=', partner_id[0]], ['company_id', '=', company_id]]], 
                            {'offset': offset, 'limit': limit, 'fields': ['id', 'name', 'description', 'stage_id', 'company_id']})
        total_tickets = execute_kw('helpdesk.ticket', 'search_count', [[['partner_id', '=', partner_id[0]], ['company_id', '=', company_id]]])
        return {'tickets': tickets, 'total': total_tickets}
    
    except Exception as e:
        logger.error(f"Error fetching tickets for email {email} and company_id {company_id}: {e}", exc_info=True)
        return {'tickets': [], 'total': 0}

def verify_customer(email, company_id):
    """Verify if the customer is valid based on email and company ID."""
    try:
        partner_id = register_email_in_odoo(email, company_id)
        return bool(partner_id)
    except Exception as e:
        logger.error(f"Error verifying customer: {e}", exc_info=True)
        return False

def get_ticket_stages():
    """Fetch the stages of a ticket in Odoo."""
    try:
        stages = execute_kw('helpdesk.stage', 'search_read', [[]], {
            'fields': ['id', 'name', 'sequence'],
            'order': 'sequence asc'
        })
        if stages:
            logger.info(f"Fetched {len(stages)} ticket stages.")
            return stages
        else:
            logger.warning("No ticket stages found.")
            return []
    except Exception as e:
        logger.error(f"Error fetching ticket stages: {e}", exc_info=True)
        return []

def get_tickets_data(email, company_id, page=1, limit=10):
    """Fetch paginated tickets by email with related messages and stage details."""
    try:
        partner_id = execute_kw('res.partner', 'search', [[['email', '=', email], ['company_id', '=', company_id]]])
        if not partner_id:
            logger.error(f"No partner found with email: {email}")
            return {'tickets': [], 'total': 0}
        
        offset = (page - 1) * limit
        tickets = execute_kw('helpdesk.ticket', 'search_read', 
                            [[['partner_id', '=', partner_id[0]], ['company_id', '=', company_id]]], 
                            {'offset': offset, 'limit': limit, 'fields': ['id', 'name', 'description', 'create_date','stage_id', 'company_id', 'partner_id']})
        
        if not tickets:
            logger.info(f"No tickets found for email: {email} and company_id: {company_id}")
            return {'tickets': [], 'total': 0}
        
        total_tickets = execute_kw('helpdesk.ticket', 'search_count', 
                                [[['partner_id', '=', partner_id[0]], ['company_id', '=', company_id]]])
        
        for ticket in tickets:
            ticket_id = ticket['id']
            stage_id, stage_name = ticket['stage_id'] if ticket['stage_id'] else (None, None)
            
            messages = execute_kw('mail.message', 'search_read', 
                                [[['res_id', '=', ticket_id], ['model', '=', 'helpdesk.ticket']]], 
                                {'fields': ['id', 'body', 'date', 'author_id']})
            
            ticket['messages'] = messages
            ticket['stage_id'] = stage_id
            ticket['stage_name'] = stage_name
        
        return {'tickets': tickets, 'total': total_tickets}
    except Exception as e:
        logger.error(f"Error fetching tickets with messages and stage for email {email} and company_id {company_id}: {e}")
        return {'tickets': [], 'total': 0}

def update_customer_email(email, new_email, company_id):
    """Update customer email in Odoo."""
    try:
        partner_id = execute_kw('res.partner', 'search', [[['email', '=', email], ['company_id', '=', company_id]]])
        if not partner_id:
            logger.error(f"No partner found with email: {email} in company ID: {company_id}")
            return False
        execute_kw('res.partner', 'write', [[partner_id[0]], {'email': new_email}])
        return True
    except Exception as e:
        logger.error(f"Error updating customer email: {e}", exc_info=True)
        return False

def add_message_to_ticket(email, company_id, ticket_id, message):
    """Add a message to an existing ticket by retrieving the partner ID using the email."""
    try:
        # Retrieve partner ID using email and company_id
        partner_id = execute_kw('res.partner', 'search', [[['email', '=', email], ['company_id', '=', company_id]]])
        
        if not partner_id:
            logger.error(f"No partner found with email: {email} and company_id: {company_id}")
            return False

        # Validate that the ticket exists and is linked to the partner
        ticket = execute_kw('helpdesk.ticket', 'search', [[['id', '=', ticket_id], ['partner_id', '=', partner_id[0]]]])
        if not ticket:
            logger.error(f"Ticket with ID {ticket_id} not found or not associated with the partner.")
            return False

        # Add the message to the ticket
        result = execute_kw('mail.message', 'create', [{
            'body': message,
            'res_id': ticket_id,
            'model': 'helpdesk.ticket',
            'author_id': partner_id[0],
        }])

        if result:
            logger.info(f"Message successfully added to ticket with ID {ticket_id} by partner {partner_id[0]}")
            return True
        else:
            logger.error("Failed to add message to the ticket.")
            return False

    except Exception as e:
        logger.error(f"Error adding message to ticket: {e}", exc_info=True)
        return False
