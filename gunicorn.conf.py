import multiprocessing

# Configuración de workers
workers = multiprocessing.cpu_count() * 2 + 1
threads = 2
worker_class = 'sync'

# Configuración de timeout
timeout = 120

# Configuración de binding
bind = "0.0.0.0:$PORT"

# Configuración de logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Configuración de worker timeout
graceful_timeout = 120
keepalive = 5
