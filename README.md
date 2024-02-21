# Odoo Helpdesk API

The Odoo Helpdesk API is a Flask-RESTx based API designed to integrate with Odoo for helpdesk ticket management. It provides endpoints for creating, updating, viewing, and deleting helpdesk tickets, as well as attaching files and managing user emails.

## Features

- **Create Tickets**: Submit new helpdesk tickets.
- **Update Tickets**: Modify existing tickets.
- **View Tickets**: List and paginate through tickets.
- **Delete Tickets**: Remove tickets from the system.
- **Attach Files**: Upload files to attach to tickets.
- **Email Registration**: Register and manage user emails for ticket updates.
- **Company Management**: List companies and view tickets by company.

## Getting Started

### Prerequisites

- Python 3.10+
- Flask, Flask-RESTx
- Access to an Odoo instance for backend management.

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/Serendeep/odoo-helpdesk.git
   cd odoo-helpdesk
   ```

2. Configure your `.env` file with your Odoo instance details. A sample `.env.example` file is provided.


### Running the Application

1. Setup a Virtual Environment: 

```
python3 -m venv venv
```

2. Activate the Virtual Environment

For Windows:
```
venv\Scripts\activate
```

For Macos and Linux
```
source venv/bin/activate
```

3. Install the Requirements:

```
pip install -r requirements.txt
```

4. Run the application:

```
python app.py
```

This starts a local development server on `http://localhost:5000`, where you can access the API endpoints.

5. To deactivate the Virtual Environment:

```
deactivate
```

Please ensure that you replace **python3** with **python** in the command to create the virtual environment if you are using Windows or if your environment recognizes **python** as **Python 3.x**.

## API Endpoints

Endpoints include:

- **POST** `/tickets/register_email`: Register a user's email.
- **POST** `/tickets/create`: Create a new ticket.
- **GET** `/tickets/view_all`: View all tickets with optional pagination.
- **GET** `/tickets/list_companies`: List all registered companies.
- **POST** `/tickets/attach_file`: Attach a file to an existing ticket.
- **PUT** `/tickets/update/<ticket_id>`: Update details of a specific ticket.
- **DELETE** `/tickets/delete/<ticket_id>`: Delete a specific ticket.
- **GET** `/tickets/by_company/<company_id>`: View tickets associated with a specific company.

## Development

Contributions to the project are welcome! Please create a branch for your contributions and submit a pull request for review.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

For questions or feedback, please contact the project maintainer at: serendeep12@gmail.com.
