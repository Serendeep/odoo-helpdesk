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
        return object_proxy.execute_kw(DB, uid, API_KEY, model, method, args, kwargs or {})
    except Exception as e:
        logger.error(f"XML-RPC Execution Error on {model}.{method}: {e}", exc_info=True)
        return None

def authenticate():
    """Retrieve the server version and user ID for the session."""
    try:
        version = common_proxy.version()
        logger.info("Successfully authenticated with Odoo.")
        return version, uid
    except Exception as e:
        logger.error(f"Authentication Error: {e}", exc_info=True)
        return None, None

def create_ticket_in_odoo(subject, description, company_id, email):
    """Create a new ticket in Odoo."""
    partner_id = register_email_in_odoo(email)
    context = {'force_company': company_id, 'allowed_company_ids': [company_id]}
    ticket_id = execute_kw('helpdesk.ticket', 'create', [{
        'name': subject,
        'description': description,
        'company_id': company_id,
        'partner_id': partner_id,
    }], {'context': context})
    if ticket_id:
        logger.info(f"Ticket created with ID: {ticket_id}")
    return ticket_id

def delete_ticket(ticket_id):
    """Delete a ticket in Odoo."""
    if execute_kw('helpdesk.ticket', 'unlink', [[ticket_id]]):
        logger.info(f"Ticket with ID {ticket_id} deleted.")
        return True
    return False

def attach_message(ticket_id, file_name, base64_content):
    """Attach a message to a ticket in Odoo."""
    attachment_id = execute_kw('ir.attachment', 'create', [{
        'name': file_name,
        'datas': base64_content,
        'store_fname': file_name,
        'res_model': 'helpdesk.ticket',
        'res_id': ticket_id
    }])
    execute_kw('mail.message', 'create', [{
            'body': 'Attachment for the ticket',
            'res_id': ticket_id,
            'model': 'helpdesk.ticket',
            'attachment_ids': [(6, 0, [attachment_id])]
        }])
    if attachment_id:
        logger.info(f"Attachment created with ID: {attachment_id} for ticket ID: {ticket_id}")
    return attachment_id

def update_ticket(ticket_id, updates):
    """Update a ticket in Odoo."""
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

def send_email_odoo(template_id, ticket_id,company_id):
    """Send an email using a predefined Odoo email template."""
    
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

def register_email_in_odoo(email):
    """Register an email in Odoo, creating a new partner if necessary."""
    partner_id = execute_kw('res.partner', 'search', [[['email', '=', email]]])
    if not partner_id:
        partner_id = [execute_kw('res.partner', 'create', [{'name': email.split('@')[0], 'email': email}])]
        logger.info(f"New partner created with ID: {partner_id[0]} for email: {email}")
    return partner_id[0]

def view_ticket(company_id):
    """View tickets for a specific company."""
    return execute_kw('helpdesk.ticket', 'search_read', [[['company_id', '=', company_id]]], {'fields': ['name', 'description', 'stage_id']})

def list_companies():
    """List all companies in Odoo."""
    return execute_kw('res.company', 'search_read', [[]], {'fields': ['id', 'name']})
