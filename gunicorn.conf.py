import multiprocessing

# Configuración de workers
workers = 2
threads = 2
worker_class = 'sync'

# Configuración de timeout
timeout = 30

# Configuración de binding
bind = "0.0.0.0:80"

# Configuración de logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Configuración de worker timeout
graceful_timeout = 30
keepalive = 5
