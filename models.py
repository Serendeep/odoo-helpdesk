from flask_restx import fields, reqparse, Model
from werkzeug.datastructures import FileStorage
from app import api


attach_parser = reqparse.RequestParser()
attach_parser.add_argument('ticket_id', type=int, required=True, help='ID of the ticket')
attach_parser.add_argument('file', location='files', type=FileStorage, required=True)

view_parser = reqparse.RequestParser()
view_parser.add_argument('page', type=int, required=False, default=1, help='Page number')
view_parser.add_argument('limit', type=int, required=False, default=10, help='Number of tickets per page')

email_parser = reqparse.RequestParser()
email_parser.add_argument('new_email', type=str, required=True, help='Updated user email address')

ticket_model = api.model('Ticket', {
    'subject': fields.String(required=True, description='The ticket subject'),
    'description': fields.String(required=True, description='The ticket description'),
})

public_ticket_model = api.model('PublicTicket', {
    'subject': fields.String(required=True, description='The ticket subject'),
    'description': fields.String(required=True, description='The ticket description'),
    'company_id': fields.Integer(required=True, description='The ID of the company'),
    'email': fields.String(required=True, description='User email for updates')
})

update_ticket_model = api.model('UpdateTicket', {
    'name': fields.String(description='The updated ticket subject'),
    'description': fields.String(description='The updated ticket description'),
    'stage_id': fields.Integer(description='The updated stage ID of the ticket'),
    'message': fields.String(description='Message to be added to the ticket')
})
