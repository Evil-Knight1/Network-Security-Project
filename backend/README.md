# Chat Application with Authentication and Admin Dashboard

A full-featured chat application with user authentication, private/group chats, React frontend, admin dashboard with email integration (SMTP/IMAP/POP3), and contact form functionality.

## Features

- **User Authentication**: Sign up and login with JWT tokens
- **Private Chats**: One-on-one messaging between users
- **Group Chats**: Create and manage group conversations
- **Real-time Messaging**: WebSocket support for instant message delivery
- **Contact Form**: Submit feedback with file attachments
- **Admin Dashboard**: 
  - View emails via IMAP or POP3 (toggleable)
  - View contact form submissions
  - Email server configuration

## Project Structure

```
.
├── server.py              # FastAPI backend server
├── database.py            # JSON database operations
├── email_service.py       # Email service (SMTP/IMAP/POP3)
├── database.json          # JSON database file (auto-created)
├── requirements.txt       # Python dependencies
├── frontend/              # React frontend
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── admin/         # Admin dashboard components
│   │   └── contexts/      # React contexts
│   └── package.json
└── README.md
```

## Setup Instructions

### Backend Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Configure email settings (optional - uses placeholders by default):
   - Edit `email_service.py` and update the `EmailConfig` class with your email server credentials
   - Or use the admin dashboard API endpoint `/api/admin/email-config` to configure

3. Start the server:
```bash
python server.py
```

The server will run on `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The frontend will run on `http://localhost:3000`

## API Endpoints

### Authentication
- `POST /api/auth/signup` - Register new user
- `POST /api/auth/login` - Login user
- `POST /api/auth/logout` - Logout user
- `GET /api/auth/me` - Get current user info

### Private Chats
- `GET /api/chats/private` - Get user's private chats
- `POST /api/chats/private?other_user_id={id}` - Create private chat
- `GET /api/chats/private/{chat_id}` - Get chat messages
- `POST /api/chats/private/{chat_id}/message?content={text}` - Send message

### Group Chats
- `GET /api/chats/groups` - Get user's groups
- `POST /api/chats/groups?name={name}` - Create group
- `GET /api/chats/groups/{group_id}` - Get group messages
- `POST /api/chats/groups/{group_id}/message?content={text}` - Send message
- `POST /api/chats/groups/{group_id}/members?user_id={id}` - Add member
- `DELETE /api/chats/groups/{group_id}/members/{user_id}` - Remove member

### Contact Form
- `POST /api/contact` - Submit contact form (multipart/form-data)

### Admin Dashboard
- `GET /api/admin/emails?limit={n}` - Get emails (IMAP/POP3)
- `POST /api/admin/email-mode?mode={IMAP|POP3}` - Toggle email mode
- `GET /api/admin/email-mode` - Get current email mode
- `GET /api/admin/contact-submissions` - Get contact submissions
- `POST /api/admin/email-config` - Update email configuration

### WebSocket
- `ws://localhost:8000/ws?token={jwt_token}` - WebSocket connection for real-time messaging

## Database

The application uses a JSON file (`database.json`) to store:
- Users (with hashed passwords)
- Private chat messages
- Group chat messages
- Contact form submissions

The database is automatically initialized when the server starts.

## Email Configuration

The email service supports:
- **SMTP**: For sending emails (contact form)
- **IMAP**: For reading emails (admin dashboard)
- **POP3**: For reading emails (admin dashboard)

Default configuration uses placeholder values. Update `email_service.py` or use the admin API to configure your email servers.

## Security Notes

- Passwords are hashed using bcrypt
- JWT tokens are used for authentication
- CORS is enabled for development (configure for production)
- Change `JWT_SECRET_KEY` in `server.py` for production use

## Development

- Backend API docs available at `http://localhost:8000/docs`
- Frontend proxy configured to forward `/api` requests to backend
- WebSocket connections require authentication token

## License

This project is for educational purposes.
