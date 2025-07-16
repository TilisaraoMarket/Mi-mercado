import os

# Configuración de workers
workers = 1
threads = 2
worker_class = 'sync'

# Configuración de timeout
timeout = 300
graceful_timeout = 300

# Configuración de binding
bind = "0.0.0.0:80"

# Configuración de logging
accesslog = '-'
errorlog = '-'
loglevel = 'debug'

# Configuración de keepalive
keepalive = 10
keepalive = 5
