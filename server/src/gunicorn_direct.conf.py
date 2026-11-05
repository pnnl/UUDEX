# this setup is for using gunicorn facing directly to outside and handling ssl (no nginx involved)

import ssl

bind = "0.0.0.0:3546"
worker_class = "server_handlers.gunicorn_handler.CustomWorker"

#### Site specific - change these parameters
ca_certs = "uudex/ssl/ca/ca.pem"
certfile = "uudex/ssl/server/server.crt"
keyfile = "uudex/ssl/server/server.key"
####

cert_reqs = ssl.CERT_REQUIRED
do_handshake_on_connect = True
