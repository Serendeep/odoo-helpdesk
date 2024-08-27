import xmlrpc.client
import logging
import re
from config import URL, DB, USERNAME, API_KEY

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

common_proxy = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
uid = common_proxy.authenticate(DB, USERNAME, API_KEY, {})
object_proxy = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')


def is_valid_email(email):
    """Validate if the provided email is in a correct format."""
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)


def execute_kw(model, method, args, kwargs=None):
    """Execute a method on an Odoo model via XML-RPC, with error handling."""
    try:
        return object_proxy.execute_kw(DB, uid, API_KEY, model, method, args, kwargs or {})
    except ConnectionRefusedError:
        logger.error(f"Failed to connect to Odoo server.")
        return None
    except TimeoutError:
        logger.error(f"Request to Odoo server timed out.")
        return None
    except Exception as e:
        logger.error(f"XML-RPC Execution Error on {model}.{method}: {e}", exc_info=True)
        return None


def authenticate():
    """Retrieve the server version and user ID for the session."""
    try:
        version = common_proxy.version()
        logger.info("Successfully authenticated with Odoo.")
        return version, uid
    except ConnectionRefusedError:
        logger.error("Failed to connect to Odoo server.")
    except TimeoutError:
        logger.error("Authentication request to Odoo server timed out.")
    except Exception as e:
        logger.error(f"Authentication Error: {e}", exc_info=True)
    return None, None


def create_ticket_in_odoo(subject, description, company_id, email):
    """Create a new ticket in Odoo, with input validation and error handling."""
    if not is_valid_email(email):
        logger.error(f"Invalid email format: {email}")
        return None

    partner_id = register_email_in_odoo(email, company_id)
    if not partner_id:
        logger.error(f"Failed to register email {email} for company {company_id}")
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
        logger.error(f"Failed to create ticket for subject: {subject}")
    
    return ticket_id


def delete_ticket(ticket_id):
    """Delete a ticket in Odoo with error handling for invalid ticket IDs."""
    if not isinstance(ticket_id, int) or ticket_id <= 0:
        logger.error(f"Invalid ticket ID: {ticket_id}")
        return False
    
    if execute_kw('helpdesk.ticket', 'unlink', [[ticket_id]]):
        logger.info(f"Ticket with ID {ticket_id} deleted.")
        return True
    else:
        logger.error(f"Failed to delete ticket with ID {ticket_id}. It may not exist.")
        return False


def attach_message(ticket_id, file_name, base64_content):
    """Attach a message to a ticket in Odoo, handling missing ticket ID and file content."""
    if not isinstance(ticket_id, int) or ticket_id <= 0:
        logger.error(f"Invalid ticket ID: {ticket_id}")
        return None

    if not file_name or not base64_content:
        logger.error("File name or content cannot be empty.")
        return None

    attachment_id = execute_kw('ir.attachment', 'create', [{
        'name': file_name,
        'datas': base64_content,
        'store_fname': file_name,
        'res_model': 'helpdesk.ticket',
        'res_id': ticket_id
    }])

    if attachment_id:
        logger.info(f"Attachment created with ID: {attachment_id} for ticket ID: {ticket_id}")
        execute_kw('mail.message', 'create', [{
            'body': 'Attachment for the ticket',
            'res_id': ticket_id,
            'model': 'helpdesk.ticket',
            'attachment_ids': [(6, 0, [attachment_id])]
        }])
    else:
        logger.error(f"Failed to create attachment for ticket ID: {ticket_id}")

    return attachment_id


def update_ticket(ticket_id, updates):
    """Update a ticket in Odoo."""
    if not isinstance(ticket_id, int) or ticket_id <= 0:
        logger.error(f"Invalid ticket ID: {ticket_id}")
        return False

    try:
        ticket_updates = {k: v for k, v in updates.items() if k != 'message'}
        result = execute_kw('helpdesk.ticket', 'write', 
                            [[ticket_id], ticket_updates])
        if 'message' in updates and updates['message']:
            execute_kw('mail.message', 'create', [{
                'body': updates['message'],
                'res_id': ticket_id,
                'model': 'helpdesk.ticket'
            }])
        return result
    except Exception as e:
        logger.error(f"Error while updating ticket: {e}")
        return False


def send_email_odoo(template_id, ticket_id, company_id):
    """Send an email using a predefined Odoo email template."""
    if not isinstance(ticket_id, int) or ticket_id <= 0:
        logger.error(f"Invalid ticket ID: {ticket_id}")
        return False

    context = {'force_company': company_id, 'allowed_company_ids': [company_id]}
    try:
        sent = execute_kw('mail.template', 'send_mail', [template_id, ticket_id],
            {'context': context}
        )
        if sent:
            logger.info("Email successfully sent through Odoo.")
            return True
    except Exception as e:
        logger.error(f"Failed to send email through Odoo: {e}")
    return False


def get_mail_templates():
    """Fetch mail templates from Odoo."""
    try:
        templates = execute_kw('mail.template', 'search_read', [[]], {'fields': ['id', 'name', 'model']})
        return templates
    except Exception as e:
        logger.error(f"Error fetching mail templates from Odoo: {e}")
        return None


def view_tickets(page, limit):
    """View a paginated list of tickets."""
    offset = (page - 1) * limit
    tickets = execute_kw('helpdesk.ticket', 'search_read', [[]], {
        'offset': offset, 'limit': limit, 'fields': ['name', 'description', 'stage_id', 'message_ids']})
    total_tickets = execute_kw('helpdesk.ticket', 'search_count', [[]])
    return {'tickets': tickets, 'total': total_tickets}


def register_email_in_odoo(email, company_id):
    """Register an email in Odoo, creating a new partner if necessary."""
    if not is_valid_email(email):
        logger.error(f"Invalid email format: {email}")
        return None

    partner_id = execute_kw('res.partner', 'search', [[['email', '=', email], ['company_id', '=', company_id]]])
    if not partner_id:
        partner_id = [execute_kw('res.partner', 'create', [{'name': email.split('@')[0], 'email': email, 'company_id': company_id}])]
        logger.info(f"New partner created with ID: {partner_id[0]} for email: {email}")
    return partner_id[0]


def list_companies(page, limit):
    """List paginated companies in Odoo."""
    offset = (page - 1) * limit
    companies = execute_kw('res.company', 'search_read', [[]], {
        'offset': offset,
        'limit': limit,
        'fields': ['id', 'name']
    })
    total_companies = execute_kw('res.company', 'search_count', [[]])
    return {'companies': companies, 'total': total_companies}


def get_ticket_by_id(ticket_id):
    """Fetch a ticket by its ID from Odoo."""
    if not isinstance(ticket_id, int) or ticket_id <= 0:
        logger.error(f"Invalid ticket ID: {ticket_id}")
        return None

    try:
        ticket = execute_kw('helpdesk.ticket', 'search_read', 
                            [[['id', '=', ticket_id]]], 
                            {'fields': ['id', 'name', 'description', 'stage_id', 'partner_id', 'message_ids']})
        return ticket[0] if ticket else None
    except Exception as e:
        logger.error(f"Error fetching ticket with ID {ticket_id}: {e}")
        return None


def get_messages_by_ticket_id(ticket_id):
    """Fetch messages by ticket ID from Odoo."""
    if not isinstance(ticket_id, int) or ticket_id <= 0:
        logger.error(f"Invalid ticket ID: {ticket_id}")
        return None

    try:
        messages = execute_kw('mail.message', 'search_read', 
                            [[['res_id', '=', ticket_id]]], 
                            {'fields': ['id', 'body']})
        return messages
    except Exception as e:
        logger.error(f"Error fetching messages for ticket with ID {ticket_id}: {e}")
        return None


def get_tickets_by_email(email, company_id, page=1, limit=10):
    """Fetch paginated tickets by email and company_id from Odoo."""
    if not is_valid_email(email):
        logger.error(f"Invalid email format: {email}")
        return None

    try:
        partner_id = execute_kw('res.partner', 'search', [[['email', '=', email], ['company_id', '=', company_id]]])
        if not partner_id:
            logger.error(f"No partner found with email: {email} and company_id: {company_id}")
            return None

        offset = (page - 1) * limit
        tickets = execute_kw('helpdesk.ticket', 'search_read', 
                            [[['partner_id', '=', partner_id[0]], ['company_id', '=', company_id]]], 
                            {'offset': offset, 'limit': limit, 'fields': ['id', 'name', 'description', 'stage_id', 'company_id']})
        total_tickets = execute_kw('helpdesk.ticket', 'search_count', [[['partner_id', '=', partner_id[0]], ['company_id', '=', company_id]]])

        return {'tickets': tickets, 'total': total_tickets}
    except Exception as e:
        logger.error(f"Error fetching tickets for email {email} and company_id {company_id}: {e}")
        return None


def verify_customer(email, company_id):
    """Verify if the customer is valid based on email and company ID."""
    if not is_valid_email(email):
        logger.error(f"Invalid email format: {email}")
        return False

    partner_id = execute_kw('res.partner', 'search', [[['email', '=', email], ['company_id', '=', company_id]]])
    return bool(partner_id)


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
            return None
    except Exception as e:
        logger.error(f"Error fetching ticket stages: {e}", exc_info=True)
        return None
