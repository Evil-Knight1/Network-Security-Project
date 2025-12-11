class EmailConfig:
    # SMTP Defaults
    SMTP_SERVER = "localhost"  # Or your lab server IP
    SMTP_PORT = 25
    SMTP_USERNAME = "ibrahim@myserver.local"
    SMTP_PASSWORD = "123456"
    SMTP_USE_TLS = False
    SMTP_USE_SSL = False

    # IMAP Defaults
    IMAP_SERVER = "localhost"
    IMAP_PORT = 143
    IMAP_USERNAME = "ibrahim@myserver.local"
    IMAP_PASSWORD = "123456"
    IMAP_USE_SSL = False

    # POP3 Defaults
    POP3_SERVER = "localhost"
    POP3_PORT = 110
    POP3_USERNAME = "ibrahim@myserver.local"
    POP3_PASSWORD = "123456"
    POP3_USE_SSL = False

    FROM_EMAIL = "ibrahim@myserver.local"
