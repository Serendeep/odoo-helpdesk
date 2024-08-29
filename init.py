from flask_restx import Api


authorizations = {
    'Bearer': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'Authorization',
        'description': 'Paste your Bearer token here'
    }
}

# Define the Api instance
api = Api(version='1.0', title='Helpdesk API', description='A simple Helpdesk API', authorizations=authorizations, doc='/docs')